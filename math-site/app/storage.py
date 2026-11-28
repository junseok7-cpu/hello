"""비공개 객체 저장소와 DB 바이트 저장."""
import os
from functools import lru_cache
from urllib.parse import urlsplit
from uuid import uuid4

from .db import Blob

EXTENSIONS = {
    "image/jpeg": ".jpg", "image/png": ".png", "application/pdf": ".pdf",
    "application/x-hwp": ".hwp", "application/hwp+zip": ".hwpx",
}


@lru_cache(maxsize=1)
def _client(endpoint, key_id, secret, region):
    import boto3
    from botocore.config import Config

    client = boto3.client("s3", endpoint_url=endpoint, aws_access_key_id=key_id,
                        aws_secret_access_key=secret, region_name=region,
                        config=Config(signature_version="s3v4",
                                  # B2는 boto3 1.36+ 기본 체크섬(aws-chunked) 업로드를 받지 않는다
                                  request_checksum_calculation="when_required",
                                  response_checksum_validation="when_required"))

    # B2는 "Expect: 100-continue" 요청에 응답하지 않고 연결을 끊는다 → 보내기 직전에 뺀다
    def _drop_expect(request, **_):
        request.headers.pop("Expect", None)

    if hasattr(client, "meta"):  # 테스트용 가짜 클라이언트는 meta 가 없다
        client.meta.events.register_first("before-send.s3.*", _drop_expect)
    return client


def _env(name):
    """붙여넣기 때 섞인 공백·줄바꿈·따옴표를 지운다."""
    return (os.getenv(name) or "").strip().strip("'\"").strip()


def key_id_hint():
    """오류 진단용: 키 ID 의 글자 수와 앞 3글자만 (비밀키는 절대 포함하지 않음)."""
    raw = os.getenv("S3_KEY_ID") or ""
    k = _env("S3_KEY_ID")
    return {"key_id_len": len(k), "key_id_prefix": k[:3], "had_spaces": raw != k}


def object_store(required=False):
    endpoint, bucket, key_id, secret = (_env(name) for name in
                                        ("S3_ENDPOINT", "S3_BUCKET", "S3_KEY_ID", "S3_SECRET"))
    if all((endpoint, bucket, key_id, secret)):
        host = urlsplit(endpoint).hostname or ""
        b2_region = host.split(".")[1] if host.startswith("s3.") and host.endswith(".backblazeb2.com") else ""
        region = os.getenv("S3_REGION") or b2_region or "us-east-1"
        return _client(endpoint, key_id, secret, region), bucket
    if required:
        raise RuntimeError("S3 설정 네 가지를 모두 입력해 주세요.")


def move_bytes(blob, store):
    client, bucket = store
    key = f"blobs/{uuid4().hex}{EXTENSIONS.get(blob.mime, '')}"
    client.put_object(Bucket=bucket, Key=key, Body=blob.data, ContentType=blob.mime)
    blob.storage_key, blob.size, blob.data = key, len(blob.data), None


def put_blob(db, data, mime):
    blob = Blob(data=data, mime=mime, size=len(data))
    if store := object_store():
        move_bytes(blob, store)
    db.add(blob)
    db.flush()
    return blob


def read_blob(blob):
    if not blob.storage_key:
        return blob.data
    client, bucket = object_store(required=True)
    body = client.get_object(Bucket=bucket, Key=blob.storage_key)["Body"]
    try:
        return body.read()
    finally:
        body.close()


def blob_url(blob):
    client, bucket = object_store(required=True)
    return client.generate_presigned_url("get_object",
                                         Params={"Bucket": bucket, "Key": blob.storage_key},
                                         ExpiresIn=300)


def delete_object(blob):
    if blob.storage_key:
        client, bucket = object_store(required=True)
        # B2는 버전 없이 삭제하면 원본을 보관한다.
        key = blob.storage_key
        pages = client.get_paginator("list_object_versions").paginate(Bucket=bucket, Prefix=key)
        versions = [v["VersionId"] for page in pages for v in page.get("Versions", [])
                    if v["Key"] == key]
        for version in versions:
            client.delete_object(Bucket=bucket, Key=key, VersionId=version)
