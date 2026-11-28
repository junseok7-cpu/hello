import io
import sys
from datetime import timedelta
from types import SimpleNamespace

import pytest
from PIL import Image
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app import storage
from test_routes import D, M, auth, client, db, prob
from tools import migrate_blobs


class FakeS3:
    def __init__(self):
        self.objects = {}
        self.signed = []

    def put_object(self, *, Bucket, Key, Body, ContentType):
        assert Bucket == "private"
        self.objects[Key] = (Body, ContentType)

    def get_object(self, *, Bucket, Key):
        assert Bucket == "private"
        return {"Body": io.BytesIO(self.objects[Key][0])}

    def generate_presigned_url(self, operation, *, Params, ExpiresIn):
        assert operation == "get_object" and Params["Bucket"] == "private" and ExpiresIn == 300
        self.signed.append(Params["Key"])
        return "https://objects.test/" + Params["Key"]

    def get_paginator(self, operation):
        assert operation == "list_object_versions"
        return self

    def paginate(self, *, Bucket, Prefix):
        assert Bucket == "private"
        yield {"Versions": [{"Key": key, "VersionId": "v"} for key in self.objects
                            if key.startswith(Prefix)]}

    def delete_object(self, *, Bucket, Key, VersionId):
        assert Bucket == "private" and VersionId == "v"
        del self.objects[Key]


@pytest.fixture
def s3(monkeypatch):
    fake = FakeS3()
    endpoint = "https://s3.us-west-004.backblazeb2.com"

    def make_client(service, **kwargs):
        assert service == "s3" and kwargs["endpoint_url"] == endpoint
        assert kwargs["region_name"] == "us-west-004"
        assert kwargs["aws_access_key_id"] == "key" and kwargs["aws_secret_access_key"] == "secret"
        return fake

    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=make_client))
    monkeypatch.setitem(sys.modules, "botocore.config", SimpleNamespace(Config=lambda **kwargs: kwargs))
    for name, value in dict(S3_ENDPOINT=endpoint, S3_BUCKET="private",
                            S3_KEY_ID="key", S3_SECRET="secret").items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("S3_REGION", raising=False)
    storage._client.cache_clear()
    yield fake
    storage._client.cache_clear()


def test_upload_and_read_private_blobs(db, client, s3):
    c, u = client
    original = c.post("/t/import", data={"title": "교재", "grade": u.grade},
                      files={"files": ("교재.hwp", b"original")})
    assert original.status_code == 303
    doc = db.get(D.Blob, int(db.query(D.ImportJob).one().blob_ids))
    assert doc.data is None and doc.size == 8 and doc.storage_key.endswith(".hwp")
    assert c.get(f"/api/grader/blob/{doc.id}", headers=auth()).content == b"original"

    photo = io.BytesIO()
    Image.new("RGB", (10, 10)).save(photo, "PNG")
    response = c.post("/api/grader/problem", headers=auth(),
                      data={"unit_id": prob(db, u.grade, "하").unit_id, "difficulty": "하"},
                      files={"image": ("그림.png", photo.getvalue())})
    assert response.status_code == 200
    problem = db.get(D.Problem, response.json()["id"])
    blob = db.get(D.Blob, problem.image_id)
    data, mime = s3.objects[blob.storage_key]
    assert blob.data is None and blob.size == len(data) and mime == "image/jpeg"
    assert c.get(f"/blob/{blob.id}").status_code == 404
    assert c.get(f"/api/grader/blob/{blob.id}").status_code == 401
    assert s3.signed == []
    u.current_problem_id = problem.id
    redirect = c.get(f"/blob/{blob.id}")
    assert redirect.status_code == 302
    assert redirect.headers["location"] == f"https://objects.test/{blob.storage_key}"
    assert s3.signed == [blob.storage_key]
    result = c.get(f"/api/grader/blob/{blob.id}", headers=auth())
    assert result.content == data and result.headers["content-type"] == mime


def test_cleanup_only_removes_expired_submission_photos(db, client, s3, monkeypatch):
    c, u = client
    problem = prob(db, u.grade, "하")
    remote = storage.put_blob(db, b"old", "image/jpeg")
    monkeypatch.delenv("S3_SECRET")
    local, recent, problem_image, ungraded, shared = [
        storage.put_blob(db, b"image", "image/jpeg") for _ in range(5)
    ]
    assert local.data == b"image" and local.size == 5 and local.storage_key is None
    monkeypatch.setenv("S3_SECRET", "secret")
    problem.image_id = problem_image.id

    def submission(status, age, *photos):
        sub = D.Submission(user_id=u.id, problem_id=problem.id, status=status,
                           graded_at=D.now() - timedelta(days=age),
                           image_ids=",".join(str(b.id) for b in photos))
        db.add(sub)
        db.flush()
        return sub

    old = submission("graded", 91, remote, local, problem_image, shared)
    newer = submission("graded", 89, recent, shared)
    waiting = submission("grading", 100, ungraded)
    monkeypatch.delitem(M.app.dependency_overrides, M.teacher)
    url = "/t/settings/delete-old-photos"
    assert c.post(url).status_code == 403
    assert c.get(f"/blob/{remote.id}").status_code == 302
    u.role = "teacher"
    html = c.get("/t/settings").text
    assert 'value="90"' in html and 'onsubmit="return confirm(' in html
    assert c.post(url, data={"days": 0}).status_code == 422
    assert c.post(url).status_code == 303
    assert old.images == [] and newer.images == [recent.id, shared.id] and waiting.images == [ungraded.id]
    assert db.get(D.Blob, remote.id) is None and db.get(D.Blob, local.id) is None
    assert db.get(D.Blob, problem_image.id) is not None and s3.objects == {}
    assert c.post(url, data={"days": 89}).status_code == 303
    assert newer.images == [] and waiting.images == [ungraded.id]


def test_migrate_legacy_blobs_and_rerun(s3, monkeypatch):
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE blobs (id INTEGER PRIMARY KEY, mime VARCHAR(60), "
                          "data BLOB NOT NULL, created_at DATETIME)"))
        conn.execute(text("INSERT INTO blobs VALUES (42, 'application/pdf', :data, NULL)"), {"data": b"pdf"})
    session = sessionmaker(bind=engine)
    monkeypatch.setattr(migrate_blobs, "engine", engine)
    monkeypatch.setattr(migrate_blobs, "SessionLocal", session)
    def fail_upload(**kwargs):
        raise OSError("업로드 실패")

    with monkeypatch.context() as failure:
        failure.setattr(s3, "put_object", fail_upload)
        with pytest.raises(OSError, match="업로드 실패"):
            migrate_blobs.migrate()
    with session() as db:
        blob = db.get(D.Blob, 42)
        assert blob.data == b"pdf" and blob.storage_key is None

    assert migrate_blobs.migrate() == 1
    assert migrate_blobs.migrate() == 0
    with session() as db:
        blob = db.get(D.Blob, 42)
        assert blob.data is None and blob.size == 3 and blob.storage_key.endswith(".pdf")
        assert s3.objects == {blob.storage_key: (b"pdf", "application/pdf")}
