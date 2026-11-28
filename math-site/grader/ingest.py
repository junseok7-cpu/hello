"""문제집·답지 파일(PDF/HWP/HWPX) → 문제 목록 (답지와 짝지음) + 확인 보고서.

채점 PC(사이트 업로드 작업)와 tools/ingest.py(Claude가 직접 처리)가 같이 쓴다.
"""
import io
import os
import re
import sys
import tempfile
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import docread  # noqa: E402
import engines  # noqa: E402
import prompts  # noqa: E402

SUBJECT_NAMES = {"math": "수학", "science": "과학"}
QTYPES = ("essay", "calc", "mc_right", "mc_wrong")


def _norm_num(n):
    return re.sub(r"(?<![0-9])0+(?=[0-9])", "", str(n or "").strip())


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
    text = (page.text or "(없음)")[:14000]
    if is_pdf and ctx.get("previous_text"):
        text = f"⟪앞 쪽의 끝부분(참고용)⟫\n{ctx['previous_text'][-800:]}\n⟪여기부터 이번 쪽⟫\n{text}"
    prompt = prompts.ANALYZE_PAGE.format(
        subject_name=SUBJECT_NAMES.get(ctx["subject"], "수학"), title=ctx["title"], grade=ctx["grade"],
        source=page.source, where=f"{page.no}쪽" if is_pdf else f"{page.no}번째 조각",
        image_note=image_note, text=text, blocks=blocks,
        figure_rule=figure_rule, figure_field=figure_field, units=ctx["units_text"])
    return engines.ask(engine, prompt, images, workdir)


def pair_answers(problems, answers):
    """구역과 번호가 같은 답지를 먼저 짝짓는다."""
    def key(item):
        return _norm_sec(item.get("section")), _norm_num(item.get("number"))

    by_key, by_num = defaultdict(list), defaultdict(list)
    for a in answers:
        by_key[key(a)].append(a)
        by_num[key(a)[1]].append(a)
    problems = [p for p in problems if not (p.get("answer") or "").strip()]
    used = set()
    num_count = defaultdict(int)
    for p in problems:
        num_count[key(p)[1]] += 1
    for exact in (True, False):
        for p in problems:
            if "_answer" in p:
                continue
            section, number = key(p)
            candidates = by_key[section, number] if exact else by_num[number]
            for a in candidates:
                if id(a) in used or (not exact and bool(section) == bool(key(a)[0])):
                    continue
                p["_answer"] = a
                used.add(id(a))
                if num_count[number] > 1 and (not exact or not section):
                    p.setdefault("_notes", []).append("번호가 겹쳐서 나온 순서대로 답지와 짝지음")
                break
    return [a for a in answers if id(a) not in used]


def _merge_figures(paths):
    from PIL import Image
    ims = [Image.open(io.BytesIO(p) if isinstance(p, bytes) else p).convert("RGB")
           for p in paths if isinstance(p, bytes) or (p and os.path.exists(p))]
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


def _norm_body(body):
    body = re.sub(r"⟦hwp:.*?⟧", "", body, flags=re.S)
    body = re.sub(r"\\(?:[,;!: ]|(?:quad|qquad|enspace|thinspace|medspace|thickspace|negthinspace)\b)", "", body)
    return "".join(c for c in body.lower()
                   if not c.isspace() and not unicodedata.category(c).startswith("P"))


def _add_note(item, note):
    item["review_note"] = " / ".join(filter(None, (item["review_note"], note)))


def _deduplicate(items, existing):
    candidates = [(_norm_body(p["body"]), p["has_image"],
                   f"기존 #{p['id']}" + (f" ({p['source']})" if p["source"] else ""), None)
                  for p in existing]
    kept, skipped = [], []
    suspected = 0
    for item in items:
        body, has_image = _norm_body(item["body"]), bool(item["image"])
        suspect = None
        for other, other_image, label, first in candidates:
            if body == other and has_image == other_image and (not has_image or len(body) >= 30):
                skipped.append(f"{item['source']} → {label}")
                if first is not None and not (first["answer"] or first["solution"]):
                    first["answer"], first["solution"] = item["answer"], item["solution"]
                break
            if suspect is None and 20 * min(len(body), len(other)) >= 9 * (len(body) + len(other)):
                if SequenceMatcher(None, other, body, autojunk=False).ratio() >= 0.90:
                    suspect = label
        else:
            if suspect is not None:
                _add_note(item, f"중복 의심: {suspect}")
                suspected += 1
            kept.append(item)
            candidates.append((body, has_image, f"같은 묶음의 {item['source']}", item))
    return kept, skipped, suspected


def _solve(item, engine, workdir):
    given = item["answer"]
    prompt = prompts.SOLVE.format(
        subject=SUBJECT_NAMES.get(item["subject"], "수학"), grade=item["grade"], unit=item["unit"],
        qtype=item["qtype"], body=item["body"], answer=given or "(없음)")
    try:
        images = []
        if item["image"]:
            with tempfile.NamedTemporaryFile(dir=workdir, suffix=".png", delete=False) as f:
                images.append(f.name)
                f.write(item["image"])
        result = engines.ask(engine, prompt, images, workdir)
        answer = result["answer"].strip()
        solution = result["solution"].strip()
        if not answer or not solution:
            raise ValueError("AI 답 또는 풀이가 비어 있음")
    except Exception as e:
        _add_note(item, f"AI 풀이 실패: {e}")
        return False
    finally:
        for path in images:
            os.unlink(path)

    item["answer"] = given or answer
    item["solution"] = "[AI 풀이] " + solution
    _add_note(item, "답지 없음 → AI 풀이 (확인 필요)")
    if given and re.sub(r"[\s$]", "", given) != re.sub(r"[\s$]", "", answer):
        _add_note(item, f"AI 답과 답지 답이 다름: AI={answer}, 답지={given}")
    if result.get("confidence") == "low":
        _add_note(item, "AI 풀이 확신 낮음")
    if result.get("note"):
        _add_note(item, str(result["note"]))
    return True


def process(files, subject, grade, title, units, engine, workdir, log=print, existing=()):
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
        previous_text = ""
        for page in pages:
            ctx["previous_text"], previous_text = previous_text, page.text
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

    # 이어지는 문제는 본문을 고르고 쪽별 영역은 보관한다.
    seen = {}
    for q in problems:
        if q.get("numbered") is False:
            continue
        page = q["_page"]
        k = (page.source, _norm_sec(q.get("section")), _norm_num(q.get("number")))
        previous, last_page = seen.get(k, (None, None))
        if previous is not None and (page.image is None or page.no == last_page + 1):
            crops = previous.get("_crops", [(previous["_page"].pdf, previous.get("bbox"))])
            inline = {field: previous.get(field) or q.get(field) for field in ("answer", "solution")}
            if len(q.get("body", "")) > len(previous.get("body", "")):
                previous.update(q)
            previous.update(inline)
            if page.image is not None:
                previous["_crops"] = crops + [(page.pdf, q.get("bbox"))]
            q["_dup"] = True
            seen[k] = previous, page.no
        else:
            seen[k] = q, page.no
    problems = [q for q in problems if not q.get("_dup")]
    leftover = pair_answers(problems, answers)

    items = []
    for q in problems:
        page = q["_page"]
        a = q.get("_answer") or {}
        answer = (q.get("answer") or "").strip() or a.get("answer") or ""
        solution = (q.get("solution") or "").strip() or a.get("solution") or ""
        rn = list(q.get("_notes", []))
        if "[도형:" in q.get("body", ""):
            rn.append("한글 도형 개체가 있어 그림이 빠졌을 수 있음 — 원본 확인")
        if q.get("unclear"):
            rn.append("AI가 확실히 못 읽은 부분: " + str(q["unclear"]))
        image, image_kind = None, "figure"
        if q.get("_crops"):
            image = _merge_figures([docread.crop_pdf(pdf, bbox) for pdf, bbox in q["_crops"] if pdf and bbox])
            image_kind = "full"
        elif q.get("has_figure") or page.image is not None and q.get("bbox") and not page.text:
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
            answer=answer if answer.strip() else "",
            solution=re.sub(r"⟦hwp:.*?⟧", "", solution).strip(),
            source=f"{title} · {page.source} {where}{sec} #{q.get('number', '')}",
            image=image, review_note=" / ".join(rn)))

    items, skipped, suspected = _deduplicate(items, existing)
    paired = sum(bool(i["answer"] or i["solution"]) for i in items)
    solved = sum(_solve(i, engine, workdir) for i in items if not i["solution"])

    # 확인 보고서
    by_sec = defaultdict(list)
    for q in problems:
        if q.get("numbered") is not False:
            by_sec[_norm_sec(q.get("section"))].append(_norm_num(q.get("number")))
    lines = [f"# 등록 보고서: {title} ({SUBJECT_NAMES.get(subject)} {grade})", "",
             f"- 문제 {len(items)}개 · 답지 연결 {paired}개 · "
             f"짝 없는 답지 {len(leftover)}개 · 확인 필요 {sum(1 for i in items if i['review_note'])}개", ""]
    lines += [f"- 중복으로 건너뜀 {len(skipped)}개"]
    lines += [f"  - {s}" for s in skipped]
    lines += [f"- 중복 의심 {suspected}개", f"- AI가 푼 문제 {solved}개 (확인 필요)"]
    lines += [f"- {s}" for s in stats]
    for sec, nums in by_sec.items():
        g = _gaps(nums)
        if g:
            lines.append(f"- ⚠️ 빠진 것 같은 번호{(' (' + sec + ')') if sec else ''}: {', '.join(map(str, g[:40]))}")
    if leftover:
        lines.append("- ⚠️ 문제를 못 찾은 답지 번호: " + ", ".join(str(a.get("number")) for a in leftover[:40]))
    lines += notes
    return items, "\n".join(lines)
