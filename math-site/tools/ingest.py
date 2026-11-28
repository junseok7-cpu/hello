"""문제집·답지 파일(PDF/HWP/HWPX)을 문제 묶음으로 만든다. (Claude가 이 저장소에서 직접 처리할 때)

    python math-site/tools/ingest.py inbox/문제.hwp inbox/답지.pdf --subject science --grade 중2 \
        --title "오투 중2-1 1단원" [--engine claude] [--upload]

결과: math-site/bundles/<title>/problems.json + img/ + report.md
--upload 를 붙이면 바로 사이트에 초안으로 올린다 (grader/config.env 의 SITE_URL, GRADER_TOKEN).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "grader"))
sys.path.insert(0, ROOT)
import engines  # noqa: E402
import ingest  # noqa: E402


def local_units(subject, grade):
    from app.curriculum import SCIENCE_UNITS, UNITS
    names = (SCIENCE_UNITS if subject == "science" else UNITS).get(grade, [])
    return [dict(id=i + 1, name=n) for i, n in enumerate(names)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--subject", choices=["math", "science"], required=True)
    ap.add_argument("--grade", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--engine", default="codex", choices=["claude", "codex"])
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--replace", action="store_true", help="같은 제목의 미제출 초안을 교체 (--upload 필요)")
    a = ap.parse_args()
    if a.replace and (not a.upload or not a.title.strip()):
        ap.error("--replace에는 --upload와 비어 있지 않은 --title이 필요합니다")

    existing = []
    if a.upload:
        import httpx
        from worker import fetch_problems, load_config
        url, tok = load_config()
        with httpx.Client(base_url=url, headers={"X-Grader-Token": tok}, timeout=60) as c:
            response = c.get("/api/grader/units", params={"grade": a.grade, "subject": a.subject})
            response.raise_for_status()
            units = response.json()
            if a.replace:
                response = c.get("/api/grader/problems", params=dict(
                    subject=a.subject, grade=a.grade, replace_source_prefix=a.title))
                response.raise_for_status()
                existing = response.json()
            else:
                existing = fetch_problems(c, a.subject, a.grade)
    else:
        units = local_units(a.subject, a.grade)
    if not units:
        sys.exit("단원 목록이 비어 있어요")

    out = os.path.join(ROOT, "bundles", re.sub(r"[^\w가-힣.-]+", "_", a.title))
    os.makedirs(os.path.join(out, "img"), exist_ok=True)
    wd = engines.new_workdir()
    try:
        items, report = ingest.process(a.files, a.subject, a.grade, a.title, units, a.engine, wd, existing=existing)
    finally:
        shutil.rmtree(wd, ignore_errors=True)
    rows = []
    for i, it in enumerate(items, 1):
        img = None
        if it["image"]:
            img = f"img/{i:04d}.png"
            with open(os.path.join(out, img), "wb") as f:
                f.write(it["image"])
        rows.append({k: v for k, v in it.items() if k not in ("image", "unit_id")} | {"image": img})
    with open(os.path.join(out, "problems.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    with open(os.path.join(out, "report.md"), "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    print(f"\n묶음: {out}")
    if a.upload:
        command = [sys.executable, os.path.join(HERE, "upload_bundle.py"), out]
        if a.replace:
            command.extend(["--replace", a.title])
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
