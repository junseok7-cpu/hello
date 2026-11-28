"""문제집·답지 파일(PDF/HWP/HWPX) → 문제 목록 (답지와 짝지음) + 확인 보고서.

채점 PC(사이트 업로드 작업)와 tools/ingest.py(Claude가 직접 처리)가 같이 쓴다.
"""
import io
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import docread  # noqa: E402
import engines  # noqa: E402
import prompts  # noqa: E402

SUBJECT_NAMES = {"math": "수학", "science": "과학"}
QTYPES = ("essay", "calc", "mc_right", "mc_wrong")


def _norm_num(n):
    s = re.sub(r"[^0-9A-Za-z가-힣]", "", str(n or ""))
    return s.lstrip("0") or s or ""


def _norm_sec(s):
    return re.sub(r"\s+", "", str(s or ""))


def analyze_page(page, ctx, engine, workdir):
    is_pdf = page.image is not None
    blocks = ""
    if page.blocks:
        lines = [f"[{x0},{y0},{x1},{y1}] {t[:90]}" for x0, y0, x1, y1, t in page.blocks[:180]]
        blocks = "\n[글자 덩어리 위치 (쪽 왼쪽 위 0,0 ~ 오른쪽 아래 1000,1000)]\n" + "\n".join(lines)
    if is_pdf:
        image_note = f"쪽 그림 파일: {os.path.basename(page.image)}" + (
            "" if page.text else " (글자 층이 없는 스캔본이라 그림에서 직접 읽어야 한다)")
        figure_rule = ("   - bbox: 쪽 그림에서 문제 전체(번호·그림·보기 포함)를 감싸는 사각형 [x0,y0,x1,y1], "
                       "비율 좌표(0~1000). 위 글자 덩어리 위치를 참고해 정확히.")
        figure_field = '"bbox": [0,0,0,0],'
        images = [page.image]
    else:
        figs = ", ".join(f"[{k}]={os.path.basename(v)}" for k, v in page.figures.items()) or "없음"
        image_note = f"이 부분에 들어 있는 그림 파일: {figs}"
        figure_rule = '   - figures: 이 문제에 딸린 그림 표시 목록 (예: ["그림3"]). 글자 속 [그림N] 위치를 보고 정한다.'
        figure_field = '"figures": [],'
        images = list(page.figures.values())
    prompt = prompts.ANALYZE_PAGE.format(
        subject_name=SUBJECT_NAMES.get(ctx["subject"], "수학"), title=ctx["title"], grade=ctx["grade"],
        source=page.source, where=f"{page.no}쪽" if is_pdf else f"{page.no}번째 조각",
        image_note=image_note, text=(page.text or "(없음)")[:14000], blocks=blocks,
        figure_rule=figure_rule, figure_field=figure_field, units=ctx["units_text"])
    return engines.ask(engine, prompt, images, workdir)


def pair_answers(problems, answers):
    """문제-답지 짝짓기: (구역, 번호)가 맞으면 그대로, 번호가 겹치면 나온 순서대로."""
    by_key = defaultdict(list)
    for a in answers:
        by_key[(_norm_sec(a.get("section")), _norm_num(a.get("number")))].append(a)
    by_num = defaultdict(list)
    for a in answers:
        by_num[_norm_num(a.get("number"))].append(a)
    used = set()
    num_count = defaultdict(int)
    for p in problems:
        num_count[_norm_num(p.get("number"))] += 1
    for p in problems:
        key = (_norm_sec(p.get("section")), _norm_num(p.get("number")))
        cand = [a for a in by_key.get(key, []) if id(a) not in used] if key[0] else []
        if not cand:
            cand = [a for a in by_num.get(key[1], []) if id(a) not in used]
            if cand and num_count[key[1]] > 1:
                p.setdefault("_notes", []).append("번호가 겹쳐서 나온 순서대로 답지와 짝지음")
        if cand:
            p["_answer"] = cand[0]
            used.add(id(cand[0]))
    return [a for a in answers if id(a) not in used]


def _merge_figures(paths):
    from PIL import Image
    ims = [Image.open(p).convert("RGB") for p in paths if os.path.exists(p)]
    if not ims:
        return None
    if len(ims) == 1:
        out = io.BytesIO()
        ims[0].save(out, "PNG")
        return out.getvalue()
    w = max(i.width for i in ims)
    canvas = Image.new("RGB", (w, sum(i.height for i in ims) + 10 * (len(ims) - 1)), "white")
    y = 0
    for i in ims:
        canvas.paste(i, (0, y))
        y += i.height + 10
    out = io.BytesIO()
    canvas.save(out, "PNG")
    return out.getvalue()


def _gaps(nums):
    ints = sorted({int(n) for n in nums if n.isdigit()})
    if len(ints) < 3:
        return []
    have = set(ints)
    return [n for n in range(ints[0], ints[-1] + 1) if n not in have]


def process(files, subject, grade, title, units, engine, workdir, log=print):
    """files: 로컬 파일 경로 목록 (문제·답지 섞여도 됨). units: [{'id','name'}]
    반환: (items, report_text). item 마다 image(bytes|None), review_note 포함."""
    ctx = dict(subject=subject, grade=grade, title=title,
               units_text="\n".join(f"- {u['id']}: {u['name']}" for u in units))
    unit_ids = {u["id"] for u in units}
    problems, answers, notes, stats = [], [], [], []
    for path in files:
        try:
            pages, meta = docread.read_any(path, workdir)
        except docread.ReadError as e:
            notes.append(f"❌ {os.path.basename(path)}: {e}")
            log(f"  {os.path.basename(path)} 읽기 실패: {e}")
            continue
        stats.append(f"{os.path.basename(path)}: {meta}")
        if meta.get("scanned"):
            notes.append(f"⚠️ {os.path.basename(path)}: 글자 층이 없는 스캔 PDF라 그림에서 읽었어요. 오타를 꼭 확인하세요.")
        for page in pages:
            try:
                res = analyze_page(page, ctx, engine, workdir)
            except Exception as e:
                notes.append(f"❌ {page.source} {page.no}: AI 분석 실패 ({e})")
                log(f"  {page.source} {page.no}: 실패 {e}")
                continue
            for q in res.get("problems") or []:
                q["_page"] = page
                problems.append(q)
            for a in res.get("answers") or []:
                answers.append(a)
            log(f"  {page.source} {page.no}: 문제 {len(res.get('problems') or [])}, 답지 {len(res.get('answers') or [])}")

    # 한글 조각 경계에서 같은 문제가 두 번 나오면 긴 쪽만 남긴다
    seen = {}
    for q in problems:
        k = (q["_page"].source, _norm_sec(q.get("section")), _norm_num(q.get("number")))
        if k in seen and q["_page"].image is None:
            if len(q.get("body", "")) > len(seen[k].get("body", "")):
                seen[k].update({kk: v for kk, v in q.items()})
            q["_dup"] = True
        else:
            seen[k] = q
    problems = [q for q in problems if not q.get("_dup")]
    leftover = pair_answers(problems, answers)

    items = []
    for q in problems:
        page = q["_page"]
        a = q.get("_answer") or {}
        rn = list(q.get("_notes", []))
        if not a:
            rn.append("답지 없음")
        if q.get("unclear"):
            rn.append("AI가 확실히 못 읽은 부분: " + str(q["unclear"]))
        image, image_kind = None, "figure"
        if q.get("has_figure") or page.image is not None and q.get("bbox") and not page.text:
            if page.pdf and q.get("bbox"):
                image, image_kind = docread.crop_pdf(page.pdf, q["bbox"]), "full"
            elif q.get("figures"):
                image = _merge_figures([page.figures[f] for f in q["figures"] if f in page.figures])
            if q.get("has_figure") and image is None:
                rn.append("그림을 못 잘라냄 — 원본 확인")
        uid = q.get("unit_id")
        if uid not in unit_ids:
            uid = units[0]["id"]
            rn.append("단원 자동 지정 실패 — 단원 확인")
        diff = q.get("difficulty") if q.get("difficulty") in ("하", "중", "상") else "중"
        where = f"p.{page.no}" if page.image else f"조각{page.no}"
        sec = f" {q.get('section')}" if q.get("section") else ""
        items.append(dict(
            subject=subject, grade=grade, unit_id=uid,
            unit=next((u["name"] for u in units if u["id"] == uid), ""),
            difficulty=diff, qtype=q.get("qtype") if q.get("qtype") in QTYPES else "essay",
            body=re.sub(r"\[그림 ?\d+\]", "(아래 그림)", re.sub(r"⟦hwp:.*?⟧", "", q.get("body", ""))).strip(),
            image_kind=image_kind,
            answer=a.get("answer", ""), solution=re.sub(r"⟦hwp:.*?⟧", "", a.get("solution", "")),
            source=f"{title} · {page.source} {where}{sec} #{q.get('number', '')}",
            image=image, review_note=" / ".join(rn)))

    # 확인 보고서
    by_sec = defaultdict(list)
    for q in problems:
        by_sec[_norm_sec(q.get("section"))].append(_norm_num(q.get("number")))
    lines = [f"# 등록 보고서: {title} ({SUBJECT_NAMES.get(subject)} {grade})", "",
             f"- 문제 {len(items)}개 · 답지 연결 {sum(1 for q in problems if q.get('_answer'))}개 · "
             f"짝 없는 답지 {len(leftover)}개 · 확인 필요 {sum(1 for i in items if i['review_note'])}개", ""]
    lines += [f"- {s}" for s in stats]
    for sec, nums in by_sec.items():
        g = _gaps(nums)
        if g:
            lines.append(f"- ⚠️ 빠진 것 같은 번호{(' (' + sec + ')') if sec else ''}: {', '.join(map(str, g[:40]))}")
    if leftover:
        lines.append("- ⚠️ 문제를 못 찾은 답지 번호: " + ", ".join(str(a.get("number")) for a in leftover[:40]))
    lines += notes
    return items, "\n".join(lines)
