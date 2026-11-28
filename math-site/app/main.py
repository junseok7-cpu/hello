"""수학 적립 학습 사이트 (FastAPI)."""
import hmac
import io
import json
import os
from datetime import datetime, timedelta
from urllib.parse import quote

from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from starlette.middleware.sessions import SessionMiddleware

from . import logic, reports, storage
from .db import (DEFAULT_SETTINGS, DIFFS, GRADES, QTYPES, SUBJECTS, KST, Blob, ImportJob, Ledger, Problem, Report,
                 SessionLocal, StudentProblem, Submission, Unit, User, get_setting,
                 init_db, kst_today, now, set_setting)

HERE = os.path.dirname(os.path.abspath(__file__))
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
GRADER_TOKEN = os.environ.get("GRADER_TOKEN", "dev-grader-token")
TEACHER_PASSWORD = os.environ.get("TEACHER_PASSWORD", "teacher")
ACCESS_KEY = os.environ.get("ACCESS_KEY", "")  # 비우면 링크 없이도 접속 가능 (로컬 테스트용)
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")

app = FastAPI(title="수학 적립 학습")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, same_site="lax",
                   https_only=BASE_URL.startswith("https"), max_age=60 * 60 * 24 * 30)
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")
tpl = Jinja2Templates(directory=os.path.join(HERE, "templates"))


def kst(dt):
    if not dt:
        return ""
    return (dt + timedelta(hours=9)).strftime("%m/%d %H:%M")


tpl.env.filters["kst"] = kst
tpl.env.globals.update(GRADES=GRADES, DIFFS=DIFFS, SUBJECTS=SUBJECTS, QTYPES=QTYPES, STUDENT_GRADES=GRADES[:4])  # 지금 학생: 중1~고1


@app.on_event("startup")
def _startup():
    secrets = ((SECRET_KEY, "dev-secret-change-me"), (TEACHER_PASSWORD, "teacher"),
               (GRADER_TOKEN, "dev-grader-token"))
    if BASE_URL.startswith("https") and any(not value.strip() or value == default for value, default in secrets):
        raise RuntimeError("운영용 비밀값을 모두 설정해 주세요")
    init_db()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Login(Exception):
    pass


@app.exception_handler(Login)
async def _to_login(request, exc):
    return RedirectResponse("/login-page", 303)


def current_user(request: Request, db=Depends(get_db)) -> User:
    uid = request.session.get("uid")
    u = db.get(User, uid) if uid else None
    if not u or not u.active:
        raise Login()
    return u


def teacher(u: User = Depends(current_user)) -> User:
    if u.role != "teacher":
        raise HTTPException(403, "선생님 전용")
    return u


def render(request, name, **ctx):
    return tpl.TemplateResponse(request, name, ctx)


def back(url):
    return RedirectResponse(url, 303)


# ---------------------------------------------------------------- 로그인
# 학생: 디스코드에 올린 링크(/join/<ACCESS_KEY>)로 들어와서 이름만 입력.
# 선생님: 비밀번호(TEACHER_PASSWORD).

def has_access(request):
    return not ACCESS_KEY or request.session.get("access") == ACCESS_KEY


@app.get("/join/{key}")
def join(key: str, request: Request):
    if ACCESS_KEY and hmac.compare_digest(key.encode(), ACCESS_KEY.encode()):
        request.session["access"] = ACCESS_KEY
        return back("/login-page")
    raise HTTPException(404)


@app.get("/login-page", response_class=HTMLResponse)
def login_page(request: Request, msg: str = ""):
    return render(request, "login.html", msg=msg, access=has_access(request))


@app.post("/login")
def login(request: Request, name: str = Form(...), db=Depends(get_db)):
    if not has_access(request):
        return back("/login-page")
    name = " ".join(name.split())
    u = db.query(User).filter(User.role == "student", User.active.is_(True), User.name == name).first()
    if not u:
        return back("/login-page?msg=" + quote("등록된 이름이 아니에요. 선생님께 물어봐 주세요."))
    request.session["uid"] = u.id
    return back("/s")


@app.post("/teacher-login")
def teacher_login(request: Request, password: str = Form(...), db=Depends(get_db)):
    if not hmac.compare_digest(password.encode(), TEACHER_PASSWORD.encode()):
        return back("/login-page?msg=" + quote("비밀번호가 틀렸어요"))
    u = db.query(User).filter_by(role="teacher").first()
    if not u:
        u = User(name="선생님", role="teacher", discord_id="teacher")
        db.add(u)
        db.commit()
    request.session["uid"] = u.id
    request.session["access"] = ACCESS_KEY
    return back("/t")


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return back("/login-page")


@app.get("/")
def home(u: User = Depends(current_user)):
    return back("/t" if u.role == "teacher" else "/s")


# ---------------------------------------------------------------- 이미지

def save_image(db, data: bytes, max_side=1800) -> int:
    """업로드 이미지를 JPEG로 줄여 저장."""
    from PIL import Image, ImageOps
    try:
        im = Image.open(io.BytesIO(data))
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((max_side, max_side))
        out = io.BytesIO()
        im.save(out, "JPEG", quality=82)
        data, mime = out.getvalue(), "image/jpeg"
    except Exception:
        raise HTTPException(400, "이미지를 읽을 수 없어요. 사진(JPG/PNG)으로 올려 주세요.")
    return storage.put_blob(db, data, mime).id


def can_see_blob(db, u: User, blob_id: int) -> bool:
    if u.role == "teacher":
        return True
    for p in db.query(Problem).filter_by(image_id=blob_id):
        if logic.is_current(u, p.id) or logic.get_sp(db, u.id, p.id):
            return True
    p = db.query(Problem).filter(Problem.solution_image_id == blob_id).first()
    if p:
        sp = logic.get_sp(db, u.id, p.id)
        return bool(sp and (sp.solution_revealed or sp.state == "solved"))
    for s in db.query(Submission).filter_by(user_id=u.id).all():
        if blob_id in s.images:
            return True
    return False


@app.get("/blob/{bid}")
def blob(bid: int, u: User = Depends(current_user), db=Depends(get_db)):
    b = db.get(Blob, bid)
    if not b or not can_see_blob(db, u, bid):
        raise HTTPException(404)
    if b.storage_key:
        return RedirectResponse(storage.blob_url(b), 302, headers={"Cache-Control": "private, no-store"})
    return Response(b.data, media_type=b.mime, headers={"Cache-Control": "private, max-age=86400"})


# ---------------------------------------------------------------- 학생

def subj(v):
    return v if v in SUBJECTS else "math"


def student_ctx(db, u, subject="math"):
    today = kst_today()
    caps = {k: dict(used=logic.used_today(db, u.id, today, k), cap=logic.cap_of(db, k)) for k in SUBJECTS}
    return dict(user=u, balance=logic.balance(db, u.id), caps=caps, subject=subject,
                used=caps[subject]["used"], cap=caps[subject]["cap"])


@app.get("/s", response_class=HTMLResponse)
def s_home(request: Request, subject: str = "math", u: User = Depends(current_user), db=Depends(get_db)):
    if u.role == "teacher":
        return back("/t")
    if not u.grade:
        return render(request, "wait_grade.html", user=u)
    subject = subj(subject)
    p = logic.current_problem(db, u, subject)
    db.commit()
    sps = [x for x in db.query(StudentProblem).filter_by(user_id=u.id).all()
           if x.problem.subject == subject]
    waiting = [x for x in sps if x.state == "waiting"]
    pending = [x for x in sps if x.state == "pending"]
    retry = [x for x in logic.retry_list(db, u.id) if x.problem.subject == subject]
    locked = [x for x in sps if x.state == "locked" and x not in retry]
    recent = [x for x in db.query(Submission).filter_by(user_id=u.id)
              .order_by(Submission.id.desc()).limit(30).all() if x.problem.subject == subject][:8]
    return render(request, "s_home.html", problem=p, waiting=waiting, pending=pending,
                  retry=retry, locked=locked, recent=recent, now=now(),
                  reward=logic.base_reward(db, p) if p else 0,
                  can_skip=logic.can_skip(u, subject), **student_ctx(db, u, subject))


@app.get("/s/p/{pid}", response_class=HTMLResponse)
def s_problem(pid: int, request: Request, u: User = Depends(current_user), db=Depends(get_db)):
    p = db.get(Problem, pid)
    if not p:
        raise HTTPException(404)
    sp = logic.get_sp(db, u.id, pid)
    if not logic.is_current(u, pid) and not sp:
        raise HTTPException(403, "아직 받지 않은 문제예요")
    subs = (db.query(Submission).filter_by(user_id=u.id, problem_id=pid)
            .order_by(Submission.id.desc()).all())
    pass_score = int(get_setting(db, "pass_score"))
    show_solution = bool(sp and (sp.solution_revealed or sp.state == "solved"))
    base = logic.base_reward(db, p)
    retry = bool(sp and (sp.is_retry or sp.state == "locked"))
    return render(request, "s_problem.html", p=p, sp=sp, subs=subs,
                  can_submit=logic.can_submit(db, u, pid), show_solution=show_solution,
                  reward=base // 2 if retry else base, QTYPES=QTYPES, pass_score=pass_score,
                  max_fails=int(get_setting(db, "max_fails")), **student_ctx(db, u, p.subject))


@app.post("/s/p/{pid}/submit")
async def s_submit(pid: int, photos: list[UploadFile] = File(...), typed_answer: str = Form(""),
                   u: User = Depends(current_user), db=Depends(get_db)):
    photos_data = [await f.read() for f in photos[:3]]
    p = db.get(Problem, pid)
    if not p or not logic.can_submit(db, u, pid):
        raise HTTPException(400, "지금은 이 문제를 제출할 수 없어요")
    ids = [save_image(db, data) for data in photos_data if data]
    if not ids:
        raise HTTPException(400, "풀이 사진을 올려 주세요")
    try:
        logic.create_submission(db, u, p, ids, typed_answer)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    db.commit()
    return back(f"/s?subject={p.subject}&sent=1")


@app.post("/s/skip")
def s_skip(subject: str = Form("math"), u: User = Depends(current_user), db=Depends(get_db)):
    subject = subj(subject)
    ok = logic.skip_problem(db, u, subject)
    db.commit()
    return back(f"/s?subject={subject}" + ("" if ok else "&noskip=1"))


@app.post("/s/appeal/{sid}")
def s_appeal(sid: int, text: str = Form(...), u: User = Depends(current_user), db=Depends(get_db)):
    s = db.get(Submission, sid)
    if not s or s.user_id != u.id or s.status != "graded" or s.appeal_status != "none":
        raise HTTPException(400)
    if s.reward_status != "rejected" and s.score is not None and s.score >= int(get_setting(db, "pass_score")):
        raise HTTPException(400)
    s.appeal_status, s.appeal_text = "open", text[:1000]
    db.commit()
    return back(f"/s/p/{s.problem_id}")


@app.get("/s/history", response_class=HTMLResponse)
def s_history(request: Request, u: User = Depends(current_user), db=Depends(get_db)):
    ledger = db.query(Ledger).filter_by(user_id=u.id).order_by(Ledger.id.desc()).limit(200).all()
    subs = db.query(Submission).filter_by(user_id=u.id).order_by(Submission.id.desc()).limit(100).all()
    return render(request, "s_history.html", ledger=ledger, subs=subs, **student_ctx(db, u))


# ---------------------------------------------------------------- 선생님

def grader_online(db):
    v = get_setting(db, "last_grader_seen")
    return bool(v) and now() - datetime.fromisoformat(v) < timedelta(minutes=3)


def weak_matrix(db, students, subject="math"):
    """학생별 단원 상태표 (요구사항 10)."""
    rows = []
    for st in students:
        if not st.grade:
            continue
        stats = logic.unit_stats(db, st.id, subject)
        cells = []
        for un in logic.eligible_units(db, st.grade, subject):
            s = stats.get(un.id, {"하": [0, 0], "중": [0, 0], "상": [0, 0]})
            n = sum(v[0] for v in s.values())
            w = sum(v[1] for v in s.values())
            cells.append(dict(unit=un, state=logic.judge_unit(db, s), s=s, n=n, w=w))
        rows.append(dict(student=st, cells=cells))
    return rows


@app.get("/t", response_class=HTMLResponse)
def t_home(request: Request, subject: str = "math", u: User = Depends(teacher), db=Depends(get_db)):
    if reports.ensure_reports(db):
        db.commit()
    subject = subj(subject)
    students = db.query(User).filter_by(role="student", active=True).order_by(User.grade, User.name).all()
    summary = []
    for st in students:
        summary.append(dict(st=st, balance=logic.balance(db, st.id),
                            today={k: logic.used_today(db, st.id, kst_today(), k) for k in SUBJECTS},
                            weak=[db.get(Unit, x) for x in logic.weak_units(db, st.id)]))
    counts = dict(
        queued=db.query(Submission).filter(Submission.status.in_(["queued", "grading"])).count(),
        pending=db.query(Submission).filter_by(reward_status="pending").count(),
        appeals=db.query(Submission).filter_by(appeal_status="open").count(),
        drafts=db.query(Problem).filter_by(status="draft").count(),
        published=db.query(Problem).filter_by(status="published").count(),
        no_grade=db.query(User).filter_by(role="student", grade=None).count())
    return render(request, "t_home.html", user=u, summary=summary, counts=counts,
                  online=grader_online(db), engine=get_setting(db, "engine"),
                  matrix=weak_matrix(db, students, subject), subject=subject)


@app.get("/t/approvals", response_class=HTMLResponse)
def t_approvals(request: Request, u: User = Depends(teacher), db=Depends(get_db)):
    subs = db.query(Submission).filter_by(reward_status="pending").order_by(Submission.id).all()
    return render(request, "t_review.html", user=u, subs=subs, mode="approve", title="상 문제 승인")


@app.post("/t/approve/{sid}")
def t_approve(sid: int, action: str = Form(...), note: str = Form(""),
              u: User = Depends(teacher), db=Depends(get_db)):
    s = db.get(Submission, sid)
    if s is None:
        raise HTTPException(404)
    if action == "approve":
        logic.approve(db, s)
    else:
        logic.reject(db, s, note)
    db.commit()
    return back("/t/approvals")


@app.get("/t/appeals", response_class=HTMLResponse)
def t_appeals(request: Request, u: User = Depends(teacher), db=Depends(get_db)):
    subs = db.query(Submission).filter_by(appeal_status="open").order_by(Submission.id).all()
    return render(request, "t_review.html", user=u, subs=subs, mode="appeal", title="이의신청")


@app.post("/t/appeal/{sid}")
def t_appeal(sid: int, action: str = Form(...), new_score: str = Form(""), note: str = Form(""),
             u: User = Depends(teacher), db=Depends(get_db)):
    s = db.get(Submission, sid)
    if s is None:
        raise HTTPException(404)
    if s.appeal_status != "open":
        return back("/t/appeals")
    try:
        score = int(new_score) if action == "accept" else None
        logic.resolve_appeal(db, s, action == "accept", score, note)
    except ValueError:
        raise HTTPException(400, "새 점수는 0~100 정수로 입력해 주세요")
    db.commit()
    return back("/t/appeals")


@app.get("/t/students", response_class=HTMLResponse)
def t_students(request: Request, u: User = Depends(teacher), db=Depends(get_db)):
    users = db.query(User).filter_by(role="student").order_by(User.active.desc(), User.grade, User.name).all()
    bal = {x.id: logic.balance(db, x.id) for x in users}
    return render(request, "t_students.html", user=u, users=users, bal=bal)


@app.post("/t/students/add")
def t_student_add(name: str = Form(...), grade: str = Form(...), u: User = Depends(teacher), db=Depends(get_db)):
    name = " ".join(name.split())
    if name and grade in GRADES and not db.query(User).filter_by(role="student", name=name).first():
        db.add(User(name=name, grade=grade, role="student", discord_id="name:" + name))
        db.commit()
    return back("/t/students")


@app.post("/t/students/{sid}")
def t_student_update(sid: int, grade: str = Form(""), active: str = Form("1"), name: str = Form(""),
                     u: User = Depends(teacher), db=Depends(get_db)):
    st = db.get(User, sid)
    if st is None:
        raise HTTPException(404)
    name = " ".join(name.split())
    if name and name != st.name and not db.query(User).filter_by(role="student", name=name).first():
        st.name = name
    st.grade = grade if grade in GRADES else None
    st.active = active == "1"
    st.current_problem_id = st.current_sci_id = None  # 학년이 바뀌면 다시 뽑기
    db.commit()
    return back("/t/students")


@app.post("/t/students/{sid}/ledger")
def t_ledger(sid: int, amount: int = Form(...), kind: str = Form("payout"), memo: str = Form(""),
             u: User = Depends(teacher), db=Depends(get_db)):
    amt = -abs(amount) if kind == "payout" else amount
    db.add(Ledger(user_id=sid, amount=amt, kind=kind, memo=memo or ("지급" if kind == "payout" else "조정")))
    db.commit()
    return back(f"/t/student/{sid}")


@app.get("/t/student/{sid}", response_class=HTMLResponse)
def t_student(sid: int, request: Request, u: User = Depends(teacher), db=Depends(get_db)):
    st = db.get(User, sid)
    if st is None:
        raise HTTPException(404)
    subs = db.query(Submission).filter_by(user_id=sid).order_by(Submission.id.desc()).limit(60).all()
    ledger = db.query(Ledger).filter_by(user_id=sid).order_by(Ledger.id.desc()).limit(60).all()
    matrix = {k: weak_matrix(db, [st], k) for k in SUBJECTS}
    return render(request, "t_student.html", user=u, st=st, subs=subs, ledger=ledger,
                  balance=logic.balance(db, sid), matrix=matrix)


@app.get("/t/sub/{sid}", response_class=HTMLResponse)
def t_sub(sid: int, request: Request, u: User = Depends(teacher), db=Depends(get_db)):
    s = db.get(Submission, sid)
    if s is None:
        raise HTTPException(404)
    return render(request, "t_review.html", user=u, subs=[s], mode="view", title=f"제출 #{sid}")


@app.post("/t/sub/{sid}/regrade")
def t_regrade(sid: int, u: User = Depends(teacher), db=Depends(get_db)):
    s = db.get(Submission, sid)
    if s is None:
        raise HTTPException(404)
    if s.status == "error":
        sp = logic.get_sp(db, s.user_id, s.problem_id)
        newer = db.query(Submission).filter_by(user_id=s.user_id, problem_id=s.problem_id).filter(Submission.id > sid)
        if sp and sp.state == "open" and not newer.first():
            sp.state = "waiting"
        s.status = "queued"
        db.commit()
    return back(f"/t/sub/{sid}")


# ----- 문제 관리

@app.get("/t/problems", response_class=HTMLResponse)
def t_problems(request: Request, subject: str = "", grade: str = "", unit: int = 0, diff: str = "", status: str = "",
               check: int = 0,
               job: int = 0, u: User = Depends(teacher), db=Depends(get_db)):
    q = db.query(Problem).join(Unit)
    if subject:
        q = q.filter(Unit.subject == subject)
    if grade:
        q = q.filter(Unit.grade == grade)
    if unit:
        q = q.filter(Problem.unit_id == unit)
    if diff:
        q = q.filter(Problem.difficulty == diff)
    if status:
        q = q.filter(Problem.status == status)
    if job:
        q = q.filter(Problem.import_job_id == job)
    if check:
        q = q.filter(Problem.review_note != "", Problem.review_note.isnot(None))
    problems = q.order_by(Problem.id.desc()).limit(300).all()
    units = db.query(Unit).order_by(Unit.grade, Unit.order).all()
    counts = (db.query(Unit.subject, Unit.grade, Problem.difficulty, func.count(Problem.id)).join(Problem)
              .filter(Problem.status == "published")
              .group_by(Unit.subject, Unit.grade, Problem.difficulty).order_by(Unit.subject, Unit.grade).all())
    return render(request, "t_problems.html", user=u, problems=problems, units=units,
                  f=dict(subject=subject, grade=grade, unit=unit, diff=diff, status=status, job=job, check=check), counts=counts)


@app.post("/t/problems/bulk")
def t_bulk(ids: list[int] = Form([]), action: str = Form(...), u: User = Depends(teacher), db=Depends(get_db)):
    for p in db.query(Problem).filter(Problem.id.in_(ids)).all():
        if action == "publish":
            p.status = "published"
        elif action == "draft":
            p.status = "draft"
        elif action == "delete" and not db.query(Submission).filter_by(problem_id=p.id).count():
            db.query(StudentProblem).filter_by(problem_id=p.id).delete()
            db.query(User).filter_by(current_problem_id=p.id).update({"current_problem_id": None})
            db.query(User).filter_by(current_sci_id=p.id).update({"current_sci_id": None})
            db.delete(p)
    db.commit()
    return back("/t/problems?status=draft" if action != "draft" else "/t/problems")


@app.get("/t/problem/{pid}", response_class=HTMLResponse)
def t_problem(pid: int, request: Request, u: User = Depends(teacher), db=Depends(get_db)):
    p = db.get(Problem, pid) if pid else None
    units = db.query(Unit).order_by(Unit.grade, Unit.order).all()
    return render(request, "t_problem.html", user=u, p=p, units=units)


@app.post("/t/problem/{pid}")
async def t_problem_save(pid: int, unit_id: int = Form(...), difficulty: str = Form(...), qtype: str = Form("essay"),
                         source: str = Form(""), body: str = Form(""), answer: str = Form(""),
                         solution: str = Form(""), status: str = Form("draft"),
                         remove_image: str = Form(""), remove_sol_image: str = Form(""), review_note: str = Form(""),
                         image: UploadFile | None = File(None), sol_image: UploadFile | None = File(None),
                         u: User = Depends(teacher), db=Depends(get_db)):
    p = db.get(Problem, pid) if pid else None
    if not p:
        p = Problem()
        db.add(p)
    p.unit_id, p.difficulty, p.source = unit_id, difficulty, source
    p.qtype = qtype if qtype in QTYPES else "essay"
    p.review_note = review_note.strip()
    p.body, p.answer, p.solution, p.status = body, answer, solution, status
    if remove_image:
        p.image_id = None
    if remove_sol_image:
        p.solution_image_id = None
    if image and image.filename:
        p.image_id = save_image(db, await image.read(), 2000)
    if sol_image and sol_image.filename:
        p.solution_image_id = save_image(db, await sol_image.read(), 2000)
    db.commit()
    return back(f"/t/problem/{p.id}?saved=1")


@app.get("/t/units", response_class=HTMLResponse)
def t_units(request: Request, u: User = Depends(teacher), db=Depends(get_db)):
    units = db.query(Unit).order_by(Unit.subject, Unit.grade, Unit.order).all()
    n = dict(db.query(Problem.unit_id, func.count(Problem.id)).group_by(Problem.unit_id).all())
    return render(request, "t_units.html", user=u, units=units, n=n)


@app.post("/t/units")
def t_units_save(action: str = Form(...), uid: int = Form(0), grade: str = Form(""), subject: str = Form("math"),
                 name: str = Form(""), order: int = Form(0), u: User = Depends(teacher), db=Depends(get_db)):
    if action == "add" and grade in GRADES and name.strip():
        db.add(Unit(subject=subj(subject), grade=grade, name=name.strip(), order=order))
    elif action == "save" and uid:
        un = db.get(Unit, uid)
        un.name, un.order = name.strip() or un.name, order
    elif action == "delete" and uid and not db.query(Problem).filter_by(unit_id=uid).count():
        db.delete(db.get(Unit, uid))
    db.commit()
    return back("/t/units")


# ----- PDF 업로드 (PC 채점 프로그램이 받아서 분류)

@app.get("/t/import", response_class=HTMLResponse)
def t_import(request: Request, u: User = Depends(teacher), db=Depends(get_db)):
    jobs = db.query(ImportJob).order_by(ImportJob.id.desc()).limit(30).all()
    n = dict(db.query(Problem.import_job_id, func.count(Problem.id)).group_by(Problem.import_job_id).all())
    return render(request, "t_import.html", user=u, jobs=jobs, n=n, online=grader_online(db))


@app.post("/t/import")
async def t_import_post(title: str = Form(...), grade: str = Form(...), subject: str = Form("math"),
                        files: list[UploadFile] = File(...), u: User = Depends(teacher), db=Depends(get_db)):
    ids, names = [], []
    for f in files:
        ext = os.path.splitext(f.filename or "")[1].lower()
        if ext not in (".pdf", ".hwp", ".hwpx"):
            raise HTTPException(400, f"PDF, HWP, HWPX만 올릴 수 있어요: {f.filename}")
        data = await f.read()
        if not data:
            continue
        b = storage.put_blob(db, data, {".pdf": "application/pdf", ".hwp": "application/x-hwp",
                                       ".hwpx": "application/hwp+zip"}[ext])
        ids.append(str(b.id))
        names.append(os.path.basename(f.filename).replace("\n", " "))
    if not ids:
        raise HTTPException(400, "파일을 골라 주세요")
    db.add(ImportJob(title=title, grade=grade, subject=subj(subject), blob_ids=",".join(ids),
                     filenames="\n".join(names)))
    db.commit()
    return back("/t/import")


# ----- 월간 보고서

@app.get("/t/reports", response_class=HTMLResponse)
def t_reports(request: Request, u: User = Depends(teacher), db=Depends(get_db)):
    if reports.ensure_reports(db):
        db.commit()
    periods = (db.query(Report.period_start, Report.period_end, func.count(Report.id))
               .group_by(Report.period_start, Report.period_end).order_by(Report.period_end.desc()).all())
    cs, ce = reports.current_period(reports.today_kst())
    return render(request, "t_reports.html", user=u, periods=periods, cur=(cs, ce))


@app.get("/t/reports/view", response_class=HTMLResponse)
def t_report_view(request: Request, end: str = "", student: int = 0, preview: int = 0,
                  u: User = Depends(teacher), db=Depends(get_db)):
    items = []
    if preview:  # 진행 중인 기간을 지금 기준으로 미리 보기 (저장 안 함)
        s, e = reports.current_period(reports.today_kst())
        for st in db.query(User).filter(User.role == "student", User.active.is_(True),
                                        User.grade.isnot(None)).order_by(User.grade, User.name):
            if not student or st.id == student:
                items.append(dict(d=reports.collect(db, st, s, e), comment="", status="preview"))
    else:
        q = db.query(Report).filter_by(period_end=end)
        if student:
            q = q.filter_by(user_id=student)
        for r in q.join(User).order_by(User.grade, User.name):
            data = reports.collect(db, r.user, r.period_start, r.period_end)
            r.data = json.dumps(data, ensure_ascii=False)
            items.append(dict(d=data, comment=r.ai_comment, status=r.status, id=r.id))
        db.commit()
    return render(request, "t_report.html", user=u, items=items, preview=preview)


@app.post("/t/reports/{rid}/comment")
def t_report_comment(rid: int, comment: str = Form(""), u: User = Depends(teacher), db=Depends(get_db)):
    r = db.get(Report, rid)
    if r is None:
        raise HTTPException(404)
    r.ai_comment, r.status = comment, "done"
    db.commit()
    return back(f"/t/reports/view?end={r.period_end}")


@app.get("/t/import/{jid}", response_class=HTMLResponse)
def t_import_report(jid: int, request: Request, u: User = Depends(teacher), db=Depends(get_db)):
    j = db.get(ImportJob, jid)
    return render(request, "t_import_report.html", user=u, j=j,
                  n=db.query(Problem).filter_by(import_job_id=jid).count(),
                  nc=db.query(Problem).filter(Problem.import_job_id == jid, Problem.review_note != "").count())


@app.get("/t/settings", response_class=HTMLResponse)
def t_settings(request: Request, u: User = Depends(teacher), db=Depends(get_db)):
    vals = {k: get_setting(db, k) for k in DEFAULT_SETTINGS if k != "last_grader_seen"}
    return render(request, "t_settings.html", user=u, vals=vals, online=grader_online(db))


@app.post("/t/settings/delete-old-photos")
def t_delete_old_photos(days: int = Form(90, ge=1, le=36500),
                        u: User = Depends(teacher), db=Depends(get_db)):
    cutoff = now() - timedelta(days=days)
    expired = {}
    kept = set()
    for sub in db.query(Submission).filter(Submission.image_ids != "").order_by(Submission.id).with_for_update():
        if sub.status == "graded" and sub.graded_at and sub.graded_at < cutoff:
            for bid in set(sub.images):
                expired.setdefault(bid, []).append(sub)
        else:
            kept.update(sub.images)
    for image_id, solution_id in db.query(Problem.image_id, Problem.solution_image_id):
        kept.update((image_id, solution_id))
    for (ids,) in db.query(ImportJob.blob_ids):
        kept.update(int(bid) for bid in (ids or "").split(",") if bid)
    for bid, submissions in expired.items():
        if bid not in kept and (blob := db.get(Blob, bid, with_for_update=True)):
            try:
                storage.delete_object(blob)
            except Exception:
                db.commit()
                raise
            db.delete(blob)
        for sub in submissions:
            sub.image_ids = ",".join(str(i) for i in sub.images if i != bid)
    db.commit()
    return back("/t/settings?photos_deleted=1")


@app.post("/t/settings")
async def t_settings_save(request: Request, u: User = Depends(teacher), db=Depends(get_db)):
    form = await request.form()
    ratios = {"mid_wrong", "hi_wrong", "weak_ratio"}
    try:
        for k in DEFAULT_SETTINGS.keys() - {"last_grader_seen", "engine"}:
            if k not in form:
                continue
            if k in ratios:
                if not 0 <= float(form[k]) <= 1:
                    raise ValueError
            else:
                int(form[k])
    except (TypeError, ValueError):
        raise HTTPException(400, "숫자 설정은 정수, 비율은 0~1로 입력해 주세요")
    for k in DEFAULT_SETTINGS:
        if k in form and k != "last_grader_seen":
            set_setting(db, k, form[k])
    db.commit()
    return back("/t/settings?saved=1")


# ---------------------------------------------------------------- 채점 PC API

def grader(request: Request):
    tok = request.headers.get("X-Grader-Token", "")
    if not hmac.compare_digest(tok.encode(), GRADER_TOKEN.encode()):
        raise HTTPException(401, "채점 토큰이 맞지 않아요")


def _seen(db):
    set_setting(db, "last_grader_seen", now().isoformat())


def problem_json(p: Problem):
    return dict(id=p.id, subject=p.subject, qtype=p.qtype, grade=p.grade, unit=p.unit.name,
                difficulty=p.difficulty, body=p.body,
                answer=p.answer, solution=p.solution, image_id=p.image_id,
                solution_image_id=p.solution_image_id)


@app.post("/api/grader/claim", dependencies=[Depends(grader)])
def g_claim(db=Depends(get_db)):
    _seen(db)
    stale = now() - timedelta(minutes=15)
    db.query(Submission).filter(Submission.status == "grading", Submission.claimed_at < stale) \
        .update({"status": "queued"})
    db.query(ImportJob).filter(ImportJob.status == "working", ImportJob.claimed_at < stale - timedelta(minutes=45)) \
        .update({"status": "queued"})
    engine = get_setting(db, "engine")
    s = db.query(Submission).filter_by(status="queued").order_by(Submission.id).first()
    if s:
        s.status, s.claimed_at = "grading", now()
        db.commit()
        return dict(type="grade", engine=engine, submission_id=s.id, images=s.images,
                    typed_answer=s.typed_answer, problem=problem_json(s.problem),
                    pass_score=int(get_setting(db, "pass_score")))
    j = db.query(ImportJob).filter_by(status="queued").order_by(ImportJob.id).first()
    if j:
        j.status, j.claimed_at = "working", now()
        units = [dict(id=x.id, name=x.name) for x in
                 db.query(Unit).filter_by(grade=j.grade, subject=j.subject or "math").order_by(Unit.order)]
        db.commit()
        return dict(type="import", engine=engine, job_id=j.id, title=j.title, grade=j.grade,
                    subject=j.subject or "math",
                    files=[dict(blob_id=int(b), name=n) for b, n in
                           zip(j.blob_ids.split(","), j.filenames.split("\n")) if b],
                    units=units)
    if reports.ensure_reports(db):
        db.flush()
    db.query(Report).filter(Report.status == "working", Report.claimed_at < stale).update({"status": "queued"})
    r = db.query(Report).filter_by(status="queued").order_by(Report.id).first()
    if r:
        r.status, r.claimed_at = "working", now()
        db.commit()
        return dict(type="report", engine=engine, report_id=r.id, data=json.loads(r.data))
    db.commit()
    return dict(type="none")


@app.get("/api/grader/blob/{bid}", dependencies=[Depends(grader)])
def g_blob(bid: int, db=Depends(get_db)):
    b = db.get(Blob, bid)
    if not b:
        raise HTTPException(404)
    return Response(storage.read_blob(b), media_type=b.mime)


@app.post("/api/grader/result/{sid}", dependencies=[Depends(grader)])
async def g_result(sid: int, request: Request, db=Depends(get_db)):
    s = db.get(Submission, sid)
    if s is None:
        raise HTTPException(404)
    try:
        data = await request.json()
    except ValueError:
        raise HTTPException(400, "채점 결과 형식을 확인해 주세요")
    db.refresh(s)
    if s.status in ("graded", "error"):
        return dict(ok=False)
    if not isinstance(data, dict):
        raise HTTPException(400, "채점 결과 형식을 확인해 주세요")
    if data.get("error"):
        if s.retry_count == 0:
            s.status, s.retry_count = "queued", 1
        else:
            s.status, s.feedback = "error", "채점 오류 — 다시 제출해 주세요"
            newer = (db.query(Submission).filter_by(user_id=s.user_id, problem_id=s.problem_id)
                     .filter(Submission.id > s.id))
            if not newer.first():
                db.query(StudentProblem).filter_by(user_id=s.user_id, problem_id=s.problem_id,
                                                   state="waiting").update({"state": "open"})
    else:
        score = data.get("score")
        if type(score) is not int or not 0 <= score <= 100:
            raise HTTPException(400, "점수는 0~100 정수여야 해요")
        logic.apply_grade(db, s, score, data.get("feedback", ""),
                          data.get("answer_read", ""), data.get("engine", ""),
                          data.get("errors", ""))
    _seen(db)
    db.commit()
    return dict(ok=True, reward_status=s.reward_status)


@app.get("/api/grader/units", dependencies=[Depends(grader)])
def g_units(grade: str = "", subject: str = "", db=Depends(get_db)):
    q = db.query(Unit)
    if grade:
        q = q.filter_by(grade=grade)
    if subject:
        q = q.filter_by(subject=subject)
    return [dict(id=x.id, subject=x.subject, grade=x.grade, name=x.name)
            for x in q.order_by(Unit.subject, Unit.grade, Unit.order)]


@app.get("/api/grader/problems", dependencies=[Depends(grader)])
def g_problems(subject: str, grade: str, replace_source_prefix: str = "", db=Depends(get_db)):
    rows = (db.query(Problem.id, Problem.body, Problem.source, Problem.image_id)
            .join(Unit).filter(Unit.subject == subject, Unit.grade == grade,
                               Problem.status.in_(("draft", "published"))).order_by(Problem.id))
    if replace_source_prefix.strip():
        rows = rows.filter(~_replaceable_draft(db, replace_source_prefix))
    return [dict(id=p.id, body=p.body or "", source=p.source or "", has_image=p.image_id is not None)
            for p in rows]


def _replaceable_draft(db, source_prefix):
    return ((Problem.status == "draft")
            & (func.substr(func.coalesce(Problem.source, ""), 1, len(source_prefix)) == source_prefix)
            & ~db.query(Submission).filter(Submission.problem_id == Problem.id).exists())


@app.post("/api/grader/problems/delete_drafts", dependencies=[Depends(grader)])
def g_delete_drafts(source_prefix: str = Body(embed=True), db=Depends(get_db)):
    if not source_prefix.strip():
        raise HTTPException(400, "source_prefix가 비어 있어요")
    drafts = db.query(Problem).filter(_replaceable_draft(db, source_prefix))
    return dict(deleted=_delete_drafts(db, drafts))


@app.post("/api/grader/problem", dependencies=[Depends(grader)])
async def g_problem(unit_id: int = Form(...), difficulty: str = Form(...), body: str = Form(""),
                    qtype: str = Form("essay"), review_note: str = Form(""), image_kind: str = Form("figure"),
                    answer: str = Form(""), solution: str = Form(""), source: str = Form(""),
                    status: str = Form("draft"), job_id: int = Form(0), skip_if_exists: int = Form(0),
                    image: UploadFile | None = File(None), sol_image: UploadFile | None = File(None),
                    db=Depends(get_db)):
    """문제 1개 등록 (PDF 자동 분류 결과 또는 Claude가 만든 묶음 업로드)."""
    if skip_if_exists and source:
        existing = db.query(Problem).filter_by(source=source).order_by(Problem.id).first()
        if existing:
            return dict(id=existing.id)
    if difficulty not in DIFFS or not db.get(Unit, unit_id):
        raise HTTPException(400, "unit/difficulty")
    p = Problem(unit_id=unit_id, difficulty=difficulty, body=body, answer=answer, solution=solution,
                qtype=qtype if qtype in QTYPES else "essay", review_note=review_note[:2000],
                image_kind="full" if image_kind == "full" else "figure",
                source=source, status=status if status in ("draft", "published") else "draft",
                import_job_id=job_id or None)
    if image and image.filename:
        p.image_id = save_image(db, await image.read(), 2000)
    if sol_image and sol_image.filename:
        p.solution_image_id = save_image(db, await sol_image.read(), 2000)
    db.add(p)
    db.commit()
    return dict(id=p.id)


@app.post("/api/grader/import/{jid}/reset", dependencies=[Depends(grader)])
def g_import_reset(jid: int, db=Depends(get_db)):
    if db.get(ImportJob, jid) is None:
        raise HTTPException(404)
    drafts = db.query(Problem).filter(
        Problem.import_job_id == jid, Problem.status == "draft",
        ~db.query(Submission).filter(Submission.problem_id == Problem.id).exists())
    _delete_drafts(db, drafts)
    return dict(ok=True)


def _delete_drafts(db, drafts):
    count = 0
    for p in drafts.order_by(Problem.id).with_for_update():
        db.query(StudentProblem).filter_by(problem_id=p.id).delete()
        db.query(User).filter_by(current_problem_id=p.id).update({"current_problem_id": None})
        db.query(User).filter_by(current_sci_id=p.id).update({"current_sci_id": None})
        db.delete(p)
        count += 1
    db.commit()
    return count


@app.post("/api/grader/import/{jid}", dependencies=[Depends(grader)])
async def g_import_done(jid: int, request: Request, db=Depends(get_db)):
    j = db.get(ImportJob, jid)
    if j is None:
        raise HTTPException(404)
    data = await request.json()
    j.status = "error" if data.get("error") else "done"
    j.log = str(data.get("log", ""))[:5000]
    j.report = str(data.get("report", ""))[:20000]
    _seen(db)
    db.commit()
    return dict(ok=True)


@app.post("/api/grader/report/{rid}", dependencies=[Depends(grader)])
async def g_report(rid: int, request: Request, db=Depends(get_db)):
    r = db.get(Report, rid)
    if r is None:
        raise HTTPException(404)
    data = await request.json()
    if data.get("error"):
        r.status = "error"  # 총평 없이 통계만 보여 준다 (선생님이 직접 써도 됨)
    else:
        r.ai_comment, r.status = str(data.get("comment", ""))[:3000], "done"
    _seen(db)
    db.commit()
    return dict(ok=True)


@app.middleware("http")
async def _grader_errors(request: Request, call_next):
    """채점 PC용 API에서 난 오류는 원인을 돌려준다 (토큰이 있어야 닿는 주소)."""
    try:
        return await call_next(request)
    except Exception as e:
        if request.url.path.startswith("/api/grader/"):
            import logging
            import traceback
            logging.getLogger("uvicorn.error").error("grader API error\n%s", traceback.format_exc())
            tok = request.headers.get("X-Grader-Token", "").encode()
            if hmac.compare_digest(tok, GRADER_TOKEN.encode()):
                body = {"error": type(e).__name__, "detail": str(e)[:500]}
                if "AccessKey" in str(e):
                    from .storage import key_id_hint
                    body["hint"] = key_id_hint()
                return JSONResponse(body, status_code=500)
        raise


@app.get("/healthz")
def healthz():
    return JSONResponse({"ok": True})
