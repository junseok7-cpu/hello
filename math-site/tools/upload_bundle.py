"""Claude가 정리한 문제 묶음을 사이트에 올린다.

묶음 폴더 구조:
    bundle/problems.json   [{"subject":"math|science", "qtype":"essay|calc|mc_right|mc_wrong", "grade":"중1","unit":"정수와 유리수","difficulty":"중","body":"...",
                             "answer":"...","solution":"...","source":"쎈 p.12 #34",
                             "image":"img/034.png", "solution_image":null}, ...]
    bundle/img/*.png

    python tools/upload_bundle.py bundle/ [--publish]
설정은 grader/config.env 의 SITE_URL, GRADER_TOKEN 을 쓴다.
"""
import argparse
import json
import os
import sys

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "grader"))
from worker import load_config  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle")
    ap.add_argument("--publish", action="store_true", help="초안 대신 바로 출제")
    a = ap.parse_args()
    url, tok = load_config()
    c = httpx.Client(base_url=url, headers={"X-Grader-Token": tok}, timeout=60)
    units = {(u["subject"], u["grade"], u["name"]): u["id"] for u in c.get("/api/grader/units").json()}
    items = json.load(open(os.path.join(a.bundle, "problems.json"), encoding="utf-8"))
    ok = 0
    for i, it in enumerate(items):
        uid = units.get((it.get("subject", "math"), it["grade"], it["unit"]))
        if not uid:
            print(f"[{i}] 단원을 못 찾음: {it['grade']} {it['unit']} — 건너뜀")
            continue
        files = {}
        for key, field in (("image", "image"), ("solution_image", "sol_image")):
            if it.get(key):
                files[field] = (os.path.basename(it[key]), open(os.path.join(a.bundle, it[key]), "rb").read())
        r = c.post("/api/grader/problem", data=dict(
            unit_id=uid, difficulty=it["difficulty"], qtype=it.get("qtype", "essay"), body=it.get("body", ""),
            review_note=it.get("review_note", ""), image_kind=it.get("image_kind", "figure"), answer=it.get("answer", ""),
            solution=it.get("solution", ""), source=it.get("source", ""),
            status="published" if a.publish else "draft"), files=files or None)
        r.raise_for_status()
        ok += 1
    print(f"{ok}/{len(items)}개 등록 완료 ({'출제' if a.publish else '초안'})")


if __name__ == "__main__":
    main()
