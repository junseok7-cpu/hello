"""선생님 PC에서 켜 두는 채점 프로그램.

사이트에서 채점할 제출물과 PDF 등록 작업을 가져와, 구독 AI(Codex/Claude CLI)로 처리하고 결과를 돌려준다.

    python worker.py            # 계속 실행 (Ctrl+C로 종료)
    python worker.py --once     # 한 건만 처리하고 종료 (테스트용)

설정: 같은 폴더의 config.env (SITE_URL, GRADER_TOKEN)
"""
import argparse
import io
import os
import shutil
import sys
import time
import traceback

import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engines  # noqa: E402
import prompts  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def load_config():
    path = os.path.join(HERE, "config.env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    url = os.environ.get("SITE_URL", "http://localhost:8000").rstrip("/")
    tok = os.environ.get("GRADER_TOKEN", "dev-grader-token")
    return url, tok


class Site:
    def __init__(self, url, token):
        self.c = httpx.Client(base_url=url, headers={"X-Grader-Token": token}, timeout=60)

    def claim(self):
        r = self.c.post("/api/grader/claim")
        r.raise_for_status()
        return r.json()

    def blob(self, bid, path):
        r = self.c.get(f"/api/grader/blob/{bid}")
        r.raise_for_status()
        with open(path, "wb") as f:
            f.write(r.content)
        return path

    def result(self, sid, data):
        self.c.post(f"/api/grader/result/{sid}", json=data).raise_for_status()

    def add_problem(self, fields, image_bytes=None):
        files = {"image": ("p.png", image_bytes, "image/png")} if image_bytes else None
        r = self.c.post("/api/grader/problem", data=fields, files=files)
        r.raise_for_status()
        return r.json()["id"]

    def report(self, rid, data):
        self.c.post(f"/api/grader/report/{rid}", json=data).raise_for_status()

    def import_done(self, jid, log, error=False):
        self.c.post(f"/api/grader/import/{jid}", json={"log": log, "error": error})


# ------------------------------------------------------------------ 채점

def grade(site: Site, job: dict):
    p = job["problem"]
    wd = engines.new_workdir()
    try:
        imgs = []
        for i, bid in enumerate(job["images"]):
            imgs.append(site.blob(bid, os.path.join(wd, f"student_{i + 1}.jpg")))
        pimg_note = sol_note = ""
        if p.get("image_id"):
            imgs.append(site.blob(p["image_id"], os.path.join(wd, "problem.jpg")))
            pimg_note = "(문제 원본 이미지: problem.jpg)"
        if p.get("solution_image_id"):
            imgs.append(site.blob(p["solution_image_id"], os.path.join(wd, "solution.jpg")))
            sol_note = "(답지 원본 이미지: solution.jpg)"
        students = ", ".join(f"student_{i + 1}.jpg" for i in range(len(job["images"])))
        prompt = prompts.GRADE.format(
            grade=p["grade"], unit=p["unit"], difficulty=p["difficulty"],
            body=p["body"] or "(문제 이미지 참고)", problem_image_note=pimg_note,
            answer=p["answer"] or "(답지 이미지 참고)", solution=p["solution"] or "(답지 이미지 참고)",
            solution_image_note=sol_note, student_images=students,
            typed_answer_note=f"학생이 따로 입력한 최종 답: {job['typed_answer']}" if job.get("typed_answer") else "")
        res = engines.ask(job["engine"], prompt, imgs, wd)
        score = int(res["score"])
        fb = res.get("feedback", "")
        errs = "\n".join("• " + str(x) for x in (res.get("logic_errors") or []))
        site.result(job["submission_id"], dict(score=score, feedback=fb, errors=errs,
                                               answer_read=str(res.get("answer_read", "")),
                                               engine=job["engine"]))
        print(f"  채점 #{job['submission_id']}: {score}점")
    except Exception as e:
        print(f"  채점 실패 #{job['submission_id']}: {e}")
        site.result(job["submission_id"], dict(error=str(e)))
    finally:
        shutil.rmtree(wd, ignore_errors=True)


# ------------------------------------------------------------------ 월간 보고서 총평

def write_report(site: Site, job: dict):
    import json
    wd = engines.new_workdir()
    try:
        res = engines.ask(job["engine"], prompts.REPORT.format(
            data=json.dumps(job["data"], ensure_ascii=False, indent=1)), [], wd)
        site.report(job["report_id"], {"comment": res.get("comment", "")})
        print(f"  보고서 #{job['report_id']} 총평 완료")
    except Exception as e:
        print(f"  보고서 #{job['report_id']} 실패: {e}")
        site.report(job["report_id"], {"error": str(e)})
    finally:
        shutil.rmtree(wd, ignore_errors=True)


# ------------------------------------------------------------------ PDF 등록

def render_pages(pdf_path, out_dir, prefix, dpi=150):
    import pymupdf
    doc = pymupdf.open(pdf_path)
    paths = []
    for i, page in enumerate(doc):
        pth = os.path.join(out_dir, f"{prefix}_{i + 1:03d}.png")
        page.get_pixmap(dpi=dpi).save(pth)
        paths.append(pth)
    return paths


def crop(png_path, bbox, pad=15):
    from PIL import Image
    im = Image.open(png_path)
    w, h = im.size
    x0, y0, x1, y1 = [max(0, min(1000, int(v))) for v in bbox]
    if x1 - x0 < 20 or y1 - y0 < 20:
        return None
    box = (max(0, (x0 - pad) * w // 1000), max(0, (y0 - pad) * h // 1000),
           min(w, (x1 + pad) * w // 1000), min(h, (y1 + pad) * h // 1000))
    out = io.BytesIO()
    im.crop(box).save(out, "PNG")
    return out.getvalue()


def norm(num):
    s = str(num).strip().lstrip("0")
    return s or "0"


def do_import(site: Site, job: dict, engine=None, log=print):
    engine = engine or job["engine"]
    wd = engines.new_workdir()
    lines = []

    def note(msg):
        lines.append(msg)
        log("  " + msg)
    try:
        units = "\n".join(f"- {u['id']}: {u['name']}" for u in job["units"])
        unit_ids = {u["id"] for u in job["units"]}
        answers = {}
        if job.get("answer_blob_id"):
            apdf = site.blob(job["answer_blob_id"], os.path.join(wd, "answers.pdf"))
            for n, img in enumerate(render_pages(apdf, wd, "ans"), 1):
                try:
                    res = engines.ask(engine, prompts.PAGE_ANSWERS.format(
                        page_image=os.path.basename(img), title=job["title"], page=n), [img], wd)
                    for a in res.get("answers", []):
                        answers[norm(a.get("number", ""))] = a
                    note(f"답지 {n}쪽: {len(res.get('answers', []))}개")
                except Exception as e:
                    note(f"답지 {n}쪽 실패: {e}")
        ppdf = site.blob(job["problem_blob_id"], os.path.join(wd, "problems.pdf"))
        total = matched = 0
        for n, img in enumerate(render_pages(ppdf, wd, "page"), 1):
            try:
                res = engines.ask(engine, prompts.PAGE_PROBLEMS.format(
                    page_image=os.path.basename(img), grade=job["grade"], title=job["title"],
                    page=n, units=units), [img], wd)
            except Exception as e:
                note(f"{n}쪽 실패: {e}")
                continue
            for q in res.get("problems", []):
                uid = q.get("unit_id")
                if uid not in unit_ids:
                    uid = job["units"][0]["id"]
                diff = q.get("difficulty") if q.get("difficulty") in ("하", "중", "상") else "중"
                a = answers.get(norm(q.get("number", "")), {})
                matched += bool(a)
                # 그림이 있는 문제만 원본을 잘라 붙인다 (없으면 글자로 보여 주는 게 깔끔)
                image = crop(img, q["bbox"]) if q.get("bbox") and q.get("has_figure") else None
                site.add_problem(dict(unit_id=uid, difficulty=diff, body=q.get("body", ""),
                                      answer=a.get("answer", ""), solution=a.get("solution", ""),
                                      source=f"{job['title']} p.{n} #{q.get('number', '')}",
                                      status="draft", job_id=job.get("job_id", 0)), image)
                total += 1
            note(f"{n}쪽: {len(res.get('problems', []))}문제")
        note(f"완료: 문제 {total}개, 답지 연결 {matched}개 → 초안으로 저장")
        if job.get("job_id"):
            site.import_done(job["job_id"], "\n".join(lines))
    except Exception as e:
        traceback.print_exc()
        if job.get("job_id"):
            site.import_done(job["job_id"], "\n".join(lines + [f"오류: {e}"]), error=True)
    finally:
        shutil.rmtree(wd, ignore_errors=True)


# ------------------------------------------------------------------ 메인 루프

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=int, default=10)
    args = ap.parse_args()
    url, tok = load_config()
    site = Site(url, tok)
    print(f"채점 프로그램 시작: {url}  (Ctrl+C로 종료)")
    while True:
        try:
            job = site.claim()
            if job["type"] == "grade":
                print(f"[채점] 제출 #{job['submission_id']} ({job['engine']})")
                grade(site, job)
                continue
            if job["type"] == "import":
                print(f"[PDF 등록] {job['title']} ({job['engine']})")
                do_import(site, job)
                continue
            if job["type"] == "report":
                print(f"[보고서] {job['data']['name']} {job['data']['start']}~{job['data']['end']}")
                write_report(site, job)
                continue
            if args.once:
                print("할 일이 없어요.")
        except httpx.HTTPError as e:
            print("사이트 연결 실패:", e)
        except KeyboardInterrupt:
            break
        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
