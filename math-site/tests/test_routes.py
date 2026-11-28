import asyncio
import json

import anyio
import httpx
import pytest

from app import main as M
from test_logic import D, L, db, prob, student, submit


class Client:
    def request(self, method, path, **kwargs):
        async def request():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=M.app),
                                         base_url="http://test") as client:
                return await client.request(method, path, **kwargs)
        return asyncio.run(request())

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)


@pytest.fixture
def client(db, monkeypatch):
    async def run_sync(func, *args, **kwargs):
        return func(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync)
    u = student(db)
    monkeypatch.setitem(M.app.dependency_overrides, M.get_db, lambda: db)
    monkeypatch.setitem(M.app.dependency_overrides, M.teacher, lambda: u)
    monkeypatch.setitem(M.app.dependency_overrides, M.current_user, lambda: u)
    return Client(), u


def auth():
    return {"X-Grader-Token": M.GRADER_TOKEN}


@pytest.mark.parametrize("key,default", [
    ("SECRET_KEY", "dev-secret-change-me"), ("TEACHER_PASSWORD", "teacher"),
    ("GRADER_TOKEN", "dev-grader-token"),
])
@pytest.mark.parametrize("empty", [False, True])
def test_https_rejects_invalid_secret(monkeypatch, key, default, empty):
    monkeypatch.setattr(M, "BASE_URL", "https://example.test")
    for name in ("SECRET_KEY", "TEACHER_PASSWORD", "GRADER_TOKEN"):
        monkeypatch.setattr(M, name, "운영용 설정")
    monkeypatch.setattr(M, key, "" if empty else default)
    with pytest.raises(RuntimeError):
        M._startup()
    monkeypatch.setattr(M, key, "별도 비밀값")
    started = []
    monkeypatch.setattr(M, "init_db", lambda: started.append(True))
    M._startup()
    assert started == [True]


def test_blob_requires_assignment_and_preserves_other_access(db, client):
    c, u = client
    p, other = [prob(db, u.grade, "하") for _ in range(2)]
    images = [D.Blob(data=b"x") for _ in range(4)]
    db.add_all(images)
    db.flush()
    p.image_id, other.image_id, p.solution_image_id, photo = [b.id for b in images]
    u.current_problem_id = p.id
    assert c.get(f"/blob/{p.image_id}").status_code == 200
    assert c.get(f"/blob/{other.image_id}").status_code == 404
    sub = L.create_submission(db, u, p, [photo])
    assert c.get(f"/blob/{p.image_id}").status_code == 200
    assert c.get(f"/blob/{photo}").status_code == 200
    assert c.get(f"/blob/{p.solution_image_id}").status_code == 404
    L.apply_grade(db, sub, 99)
    assert c.get(f"/blob/{p.solution_image_id}").status_code == 200


@pytest.mark.parametrize("method,path,payload", [
    ("post", "/t/approve/999", {"action": "approve"}),
    ("post", "/t/appeal/999", {"action": "accept"}),
    ("post", "/t/sub/999/regrade", {}),
    ("post", "/t/reports/999/comment", {}),
    ("get", "/t/student/999", {}),
    ("get", "/t/sub/999", {}),
    ("post", "/t/students/999", {}),
    ("post", "/api/grader/result/999", {}),
    ("post", "/api/grader/report/999", {}),
    ("post", "/api/grader/import/999", {}),
])
def test_missing_ids_return_404(client, method, path, payload):
    c, _ = client
    args = {"json": payload} if path.startswith("/api/") else {"data": payload}
    assert c.request(method, path, headers=auth(), **args).status_code == 404


def test_appeal_validates_score_and_renders_rejected_button(db, client):
    c, u = client
    p = prob(db, u.grade, "상")
    sub = submit(db, u, p, 95)
    L.reject(db, sub)
    path = f"/s/p/{p.id}"
    assert "<summary>이의신청</summary>" in c.get(path).text
    assert c.post(f"/s/appeal/{sub.id}", data={"text": "풀이를 확인해 주세요"}).status_code == 303
    for value in ("", "²", "91.5", "101", "-1"):
        r = c.post(f"/t/appeal/{sub.id}", data={"action": "accept", "new_score": value})
        assert r.status_code == 400 and sub.appeal_status == "open"
    assert c.post(f"/t/appeal/{sub.id}", data={"action": "accept", "new_score": "93"}).status_code == 303
    assert (sub.appeal_status, sub.score, sub.reward_status) == ("accepted", 93, "pending")
    assert "<summary>이의신청</summary>" not in c.get(path).text
    assert c.post(f"/t/appeal/{sub.id}", data={"action": "reject"}).status_code == 303
    assert sub.appeal_status == "accepted"


def test_grading_error_retries_then_reopens_and_validates_score(db, client):
    c, u = client
    p = prob(db, u.grade, "하")
    s = L.create_submission(db, u, p, [])
    sp = L.get_sp(db, u.id, p.id)
    path = f"/api/grader/result/{s.id}"
    for payload in ({}, {"score": True}, {"score": 90.0}, {"score": "90"}, {"score": 101}):
        assert c.post(path, headers=auth(), json=payload).status_code == 400
    assert c.post(path, headers=auth(), json={"error": "실패"}).json()["ok"]
    assert (s.status, s.retry_count, sp.state) == ("queued", 1, "waiting")
    assert c.post("/api/grader/claim", headers=auth()).json()["submission_id"] == s.id
    assert c.post(path, headers=auth(), json={"error": "실패"}).json()["ok"]
    assert (s.status, sp.state, sp.fail_count) == ("error", "open", 0)
    assert "채점 오류 — 다시 제출해 주세요" in c.get(f"/s/p/{p.id}").text
    retry = L.create_submission(db, u, p, [])
    path = f"/api/grader/result/{retry.id}"
    assert c.post(path, headers=auth(), json={"score": 95}).json()["ok"]
    assert c.post(path, headers=auth(), json={"score": 95}).json() == {"ok": False}
    assert L.balance(db, u.id) == 10


def test_digest_handles_non_ascii_inputs(db, client, monkeypatch):
    c, _ = client
    monkeypatch.setattr(M, "ACCESS_KEY", "참가")
    monkeypatch.setattr(M, "TEACHER_PASSWORD", "교사")
    assert c.get("/join/참가").status_code == 303
    assert c.get("/join/다름").status_code == 404
    assert c.post("/teacher-login", data={"password": "교사"}).headers["location"] == "/t"
    assert c.post("/api/grader/claim", headers={"X-Grader-Token": "é".encode("utf-8")}).status_code == 401


@pytest.mark.parametrize("key,bad", [
    *((key, "1.5") for key in ("cap_math", "cap_science", "reward_science", "pass_score",
                               "max_fails", "lock_days", "mid_sample", "hi_sample")),
    ("mid_wrong", "nan"), ("hi_wrong", "-0.1"), ("weak_ratio", "1.1"),
])
def test_invalid_settings_are_not_saved(db, client, key, bad):
    c, _ = client
    r = c.post("/t/settings", data={"engine": "claude", key: bad})
    assert r.status_code == 400 and "0~1" in r.json()["detail"]
    assert D.get_setting(db, "engine") == "codex"
    assert D.get_setting(db, key) == D.DEFAULT_SETTINGS[key]


def test_report_view_refreshes_data_and_keeps_comment(db, client):
    c, u = client
    s = submit(db, u, prob(db, u.grade, "하"), 95)
    r = D.Report(user_id=u.id, period_start=s.kst_date, period_end=s.kst_date,
                 data="{}", ai_comment="기존 총평", status="done")
    db.add(r)
    db.flush()
    response = c.get("/t/reports/view", params={"end": r.period_end})
    assert response.status_code == 200 and "기존 총평" in response.text
    assert json.loads(r.data)["subjects"]["math"]["passed"] == 1 and r.status == "done"


def test_import_reset_and_source_dedup(db, client):
    c, u = client
    job, other = D.ImportJob(), D.ImportJob()
    db.add_all([job, other])
    db.flush()
    deleted, used, published, different_job = [prob(db, u.grade, "하") for _ in range(4)]
    for p in (deleted, used, published):
        p.import_job_id = job.id
    different_job.import_job_id = other.id
    submit(db, u, used, 95)
    for p in (deleted, used, different_job):
        p.status = "draft"
    fields = dict(source="교재 1번", skip_if_exists=1, difficulty="하", unit_id=used.unit_id)
    url = "/api/grader/problem"
    first = c.post(url, headers=auth(), data=fields).json()
    assert c.post(url, headers=auth(), data={**fields, "body": "새 본문"}).json() == first
    assert db.query(D.Problem).filter_by(source=fields["source"]).one().body == ""
    assert c.post(f"/api/grader/import/{job.id}/reset", headers=auth()).json()["ok"]
    assert db.get(D.Problem, deleted.id) is None
    assert all(db.get(D.Problem, p.id) for p in (used, published, different_job))


def test_full_image_exposes_problem_text(db, client):
    c, u = client
    p = prob(db, u.grade, "하")
    u.current_problem_id = p.id
    p.image_id, p.image_kind, p.body = 999, "full", "본문 검증"
    html = c.get(f"/s/p/{p.id}").text
    assert html.index('src="/blob/999"') < html.index("<summary>글로 보기</summary>") < html.index("본문 검증")


def test_grader_problems_requires_token_and_filters_by_subject_grade(db, client):
    c, _ = client
    published = prob(db, "중1", "하")
    draft = prob(db, "중1", "중", i=1)
    image = D.Blob(data=b"image")
    db.add(image)
    db.flush()
    draft.status, draft.image_id, draft.source = "draft", image.id, "교재"
    prob(db, "중2", "하")
    prob(db, "중1", "하", subject="science")
    url = "/api/grader/problems?subject=math&grade=중1"
    assert c.get(url).status_code == 401
    response = c.get(url, headers=auth())
    assert response.status_code == 200
    assert response.json() == [
        dict(id=published.id, body="x", source="", has_image=False),
        dict(id=draft.id, body="x", source="교재", has_image=True),
    ]
