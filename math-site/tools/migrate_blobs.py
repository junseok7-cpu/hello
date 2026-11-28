"""DB의 파일 바이트를 비공개 객체 저장소로 옮긴다."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import Blob, SessionLocal, engine, migrate_blob_schema
from app.storage import move_bytes, object_store


def migrate():
    store = object_store(required=True)
    with engine.begin() as conn:
        migrate_blob_schema(conn)
    count, last_id = 0, None
    with SessionLocal() as db:
        while True:
            rows = db.query(Blob).filter(Blob.data.is_not(None), Blob.storage_key.is_(None))
            if last_id is not None:
                rows = rows.filter(Blob.id > last_id)
            blob = rows.order_by(Blob.id).with_for_update().first()
            if blob is None:
                return count
            move_bytes(blob, store)
            last_id = blob.id
            db.commit()
            count += 1


if __name__ == "__main__":
    if not os.getenv("DATABASE_URL"):
        sys.exit("DATABASE_URL을 설정해 주세요.")
    print(f"옮긴 파일: {migrate()}개")
