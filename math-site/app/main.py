"""수학 적립 학습 사이트 (FastAPI)."""
import hmac
import io
import json
import os
from datetime import datetime, timedelta
from urllib.parse import quote

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from starlette.middleware.sessions import SessionMiddleware

from . import logic, reports
from .db import (DEFAULT_SETTINGS, DIFFS, GRADES, KST, Blob, ImportJob, Ledger, Problem, Report,
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
tpl.env.globals.update(GRADES=GRADES, DIFFS=DIFFS, STUDENT_GRADES=GRADES[:4])  # 지금 학생: 중1~고1


@app.on_event("startup")
def _startup():
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
    if ACCESS_KEY and hmac.compare_digest(key, ACCESS_KEY):
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
    if not hmac.compare_digest(password, TEACHER_PASSWORD):
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
    b = Blob(data=data, mime=mime)
    db.add(b)
    db.flush()
    return b.id


def can_see_blob(db, u: User, blob_id: int) -> bool:
    if u.role == "teacher":
        return True
    if db.query(Problem).filter(Problem.image_id == blob_id, Problem.status == "published").count():
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
    return Response(b.data, media_type=b.mime, headers={"Cache-Control": "private, max-age=86400"})


# ---------------------------------------------------------------- 학생

def student_ctx(db, u):
    today = kst_today()
    cap = int(get_setting(db, "daily_cap"))
    return dict(user=u, balance=logic.balance(db, u.id), used=logic.used_today(db, u.id, today), cap=cap)


@app.get("/s", response_class=HTMLResponse)
def s_home(request: Request, u: User = Depends(current_user), db=Depends(get_db)):
    if u.role == "teacher":
        return back("/t")
    if not u.grade:
        return render(request, "wait_grade.html", user=u)
    p = logic.current_problem(db, u)
    db.commit()
    sps = db.query(StudentProblem).filter_by(user_id=u.id).all()
    waiting = [x for x in sps if x.state == "waiting"]
    pending = [x for x in sps if x.state == "pending"]
    retry = logic.retry_list(db, u.id)
    locked = [x for x in sps if x.state == "locked" and x not in retry]
    recent = (db.query(Submission).filter_by(user_id=u.id)
              .order_by(Submission.id.desc()).limit(8).all())
    return render(request, "s_home.html", problem=p, waiting=waiting, pending=pending,
                  retry=retry, locked=locked, recent=recent, now=now(),
                  can_skip=logic.can_skip(u), **student_ctx(db, u))


@app.get("/s/p/{pid}", response_class=HTMLResponse)
def s_problem(pid: int, request: Request, u: User = Depends(current_user), db=Depends(get_db)):
    p = db.get(Problem, pid)
    if not p:
        raise HTTPException(404)
    sp = logic.get_sp(db, u.id, pid)
    if u.current_problem_id != pid and not sp:
        raise HTTPException(403, "아직 받지 않은 문제예요")
    subs = (db.query(Submission).filter_by(user_id=u.id, problem_id=pid)
            .order_by(Submission.id.desc()).all())
    show_solution = bool(sp and (sp.solution_revealed or sp.state == "solved"))
    return render(request, "s_problem.html", p=p, sp=sp, subs=subs,
                  can_submit=logic.can_submit(db, u, pid), show_solution=show_solution,
                  max_fails=int(get_setting(db, "max_fails")), **student_ctx(db, u))


@app.post("/s/p/{pid}/submit")
async def s_submit(pid: int, photos: list[UploadFile] = File(...), typed_answer: str = Form(""),
                   u: User = Depends(current_user), db=Depends(get_db)):
    p = db.get(Problem, pid)
    if not p or not logic.can_submit(db, u, pid):
        raise HTTPException(400, "지금은 이 문제를 제출할 수 없어요")
    ids = []
    for f in photos[:3]:
        data = await f.read()
        if data:
            ids.append(save_image(db, data))
    if not ids:
        raise HTTPException(400, "풀이 사진을 올려 주세요")
    logic.create_submission(db, u, p, ids, typed_answer)
    db.commit()
    return back("/s?sent=1")


@app.post("/s/skip")
def s_skip(u: User = Depends(current_user), db=Depends(get_db)):
    ok = logic.skip_problem(db, u)
    db.commit()
    return back("/s" if ok else "/s?noskip=1")


@app.post("/s/appeal/{sid}")
def s_appeal(sid: int, text: str = Form(...), u: User = Depends(current_user), db=Depends(get_db)):
    s = db.get(Submission, sid)
    if not s or s.user_id != u.id or s.status != "graded" or s.appeal_status != "none":
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


def weak_matrix(db, students):
    """학생별 단원 상태표 (요구사항 10)."""
    rows = []
    for st in students:
        if not st.grade:
            continue
        stats = logic.unit_stats(db, st.id)
        cells = []
        for un in logic.eligible_units(db, st.grade):
            s = stats.get(un.id, {"하": [0, 0], "중": [0, 0], "상": [0, 0]})
            n = sum(v[0] for v in s.values())
            w = sum(v[1] for v in s.values())
            cells.append(dict(unit=un, state=logic.judge_unit(db, s), s=s, n=n, w=w))
        rows.append(dict(student=st, cells=cells))
    return rows


@app.get("/t", response_class=HTMLResponse)
def t_home(request: Request, u: User = Depends(teacher), db=Depends(get_db)):
    if reports.ensure_reports(db):
        db.commit()
    students = db.query(User).filter_by(role="student", active=True).order_by(User.grade, User.name).all()
    summary = []
    for st in students:
        summary.append(dict(st=st, balance=logic.balance(db, st.id),
                            today=logic.used_today(db, st.id, kst_today()),
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
                  matrix=weak_matrix(db, students))


@app.get("/t/approvals", response_class=HTMLResponse)
def t_approvals(request: Request, u: User = Depends(teacher), db=Depends(get_db)):
    subs = db.query(Submission).filter_by(reward_status="pending").order_by(Submission.id).all()
    return render(request, "t_review.html", user=u, subs=subs, mode="approve", title="상 문제 승인")


@app.post("/t/approve/{sid}")
def t_approve(sid: int, action: str = Form(...), note: str = Form(""),
              u: User = Depends(teacher), db=Depends(get_db)):
    s = db.get(Submission, sid)
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
    score = int(new_score) if new_score.strip().isdigit() else None
    logic.resolve_appeal(db, s, action == "accept", score, note)
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
    name = " ".join(name.split())
    if name and name != st.name and not db.query(User).filter_by(role="student", name=name).first():
        st.name = name
    st.grade = grade if grade in GRADES else None
    st.active = active == "1"
    st.current_problem_id = None  # 학년이 바뀌면 다시 뽑기
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
    subs = db.query(Submission).filter_by(user_id=sid).order_by(Submission.id.desc()).limit(60).all()
    ledger = db.query(Ledger).filter_by(user_id=sid).order_by(Ledger.id.desc()).limit(60).all()
    matrix = weak_matrix(db, [st])
    return render(request, "t_student.html", user=u, st=st, subs=subs, ledger=ledger,
                  balance=logic.balance(db, sid), matrix=matrix)


@app.get("/t/sub/{sid}", response_class=HTMLResponse)
def t_sub(sid: int, request: Request, u: User = Depends(teacher), db=Depends(get_db)):
    s = db.get(Submission, sid)
    return render(request, "t_review.html", user=u, subs=[s], mode="view", title=f"제출 #{sid}")


@app.post("/t/sub/{sid}/regrade")
def t_regrade(sid: int, u: User = Depends(teacher), db=Depends(get_db)):
    s = db.get(Submission, sid)
    if s.status == "error":
        s.status = "queued"
        db.commit()
    return back(f"/t/sub/{sid}")


# ----- 문제 관리

@app.get("/t/problems", response_class=HTMLResponse)
def t_problems(request: Request, grade: str = "", unit: int = 0, diff: str = "", status: str = "",
               job: int = 0, u: User = Depends(teacher), db=Depends(get_db)):
    q = db.query(Problem).join(Unit)
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
    problems = q.order_by(Problem.id.desc()).limit(300).all()
    units = db.query(Unit).order_by(Unit.grade, Unit.order).all()
    counts = (db.query(Unit.grade, Problem.difficulty, func.count(Problem.id)).join(Problem)
              .filter(Problem.status == "published").group_by(Unit.grade, Problem.difficulty).all())
    return render(request, "t_problems.html", user=u, problems=problems, units=units,
                  f=dict(grade=grade, unit=unit, diff=diff, status=status, job=job), counts=counts)


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
            db.delete(p)
    db.commit()
    return back("/t/problems?status=draft" if action != "draft" else "/t/problems")


@app.get("/t/problem/{pid}", response_class=HTMLResponse)
def t_problem(pid: int, request: Request, u: User = Depends(teacher), db=Depends(get_db)):
    p = db.get(Problem, pid) if pid else None
    units = db.query(Unit).order_by(Unit.grade, Unit.order).all()
    return render(request, "t_problem.html", user=u, p=p, units=units)


@app.post("/t/problem/{pid}")
async def t_problem_save(pid: int, unit_id: int = Form(...), difficulty: str = Form(...),
                         source: str = Form(""), body: str = Form(""), answer: str = Form(""),
                         solution: str = Form(""), status: str = Form("draft"),
                         remove_image: str = Form(""), remove_sol_image: str = Form(""),
                         image: UploadFile | None = File(None), sol_image: UploadFile | None = File(None),
                         u: User = Depends(teacher), db=Depends(get_db)):
    p = db.get(Problem, pid) if pid else None
    if not p:
        p = Problem()
        db.add(p)
    p.unit_id, p.difficulty, p.source = unit_id, difficulty, source
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
    units = db.query(Unit).order_by(Unit.grade, Unit.order).all()
    n = dict(db.query(Problem.unit_id, func.count(Problem.id)).group_by(Problem.unit_id).all())
    return render(request, "t_units.html", user=u, units=units, n=n)


@app.post("/t/units")
def t_units_save(action: str = Form(...), uid: int = Form(0), grade: str = Form(""),
                 name: str = Form(""), order: int = Form(0), u: User = Depends(teacher), db=Depends(get_db)):
    if action == "add" and grade in GRADES and name.strip():
        db.add(Unit(grade=grade, name=name.strip(), order=order))
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
async def t_import_post(title: str = Form(...), grade: str = Form(...), problems: UploadFile = File(...),
                        answers: UploadFile | None = File(None), u: User = Depends(teacher), db=Depends(get_db)):
    def put(data, mime):
        b = Blob(data=data, mime=mime)
        db.add(b)
        db.flush()
        return b.id
    pdata = await problems.read()
    job = ImportJob(title=title, grade=grade, problem_blob_id=put(pdata, "application/pdf"))
    if answers and answers.filename:
        job.answer_blob_id = put(await answers.read(), "application/pdf")
    db.add(job)
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
            items.append(dict(d=json.loads(r.data), comment=r.ai_comment, status=r.status, id=r.id))
    return render(request, "t_report.html", user=u, items=items, preview=preview)


@app.post("/t/reports/{rid}/comment")
def t_report_comment(rid: int, comment: str = Form(""), u: User = Depends(teacher), db=Depends(get_db)):
    r = db.get(Report, rid)
    r.ai_comment, r.status = comment, "done"
    db.commit()
    return back(f"/t/reports/view?end={r.period_end}")


@app.get("/t/settings", response_class=HTMLResponse)
def t_settings(request: Request, u: User = Depends(teacher), db=Depends(get_db)):
    vals = {k: get_setting(db, k) for k in DEFAULT_SETTINGS if k != "last_grader_seen"}
    return render(request, "t_settings.html", user=u, vals=vals, online=grader_online(db))


@app.post("/t/settings")
async def t_settings_save(request: Request, u: User = Depends(teacher), db=Depends(get_db)):
    form = await request.form()
    for k in DEFAULT_SETTINGS:
        if k in form and k != "last_grader_seen":
            set_setting(db, k, form[k])
    db.commit()
    return back("/t/settings?saved=1")


# ---------------------------------------------------------------- 채점 PC API

def grader(request: Request):
    tok = request.headers.get("X-Grader-Token", "")
    if not hmac.compare_digest(tok, GRADER_TOKEN):
        raise HTTPException(401, "bad grader token")


def _seen(db):
    set_setting(db, "last_grader_seen", now().isoformat())


def problem_json(p: Problem):
    return dict(id=p.id, grade=p.grade, unit=p.unit.name, difficulty=p.difficulty, body=p.body,
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
                 db.query(Unit).filter_by(grade=j.grade).order_by(Unit.order)]
        db.commit()
        return dict(type="import", engine=engine, job_id=j.id, title=j.title, grade=j.grade,
                    problem_blob_id=j.problem_blob_id, answer_blob_id=j.answer_blob_id, units=units)
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
    return Response(b.data, media_type=b.mime)


@app.post("/api/grader/result/{sid}", dependencies=[Depends(grader)])
async def g_result(sid: int, request: Request, db=Depends(get_db)):
    data = await request.json()
    s = db.get(Submission, sid)
    if not s or s.status == "graded":
        return dict(ok=False)
    if data.get("error"):
        s.status, s.feedback = "error", "채점 오류: " + str(data["error"])[:500]
    else:
        logic.apply_grade(db, s, int(data["score"]), data.get("feedback", ""),
                          data.get("answer_read", ""), data.get("engine", ""),
                          data.get("errors", ""))
    _seen(db)
    db.commit()
    return dict(ok=True, reward_status=s.reward_status)


@app.get("/api/grader/units", dependencies=[Depends(grader)])
def g_units(grade: str = "", db=Depends(get_db)):
    q = db.query(Unit)
    if grade:
        q = q.filter_by(grade=grade)
    return [dict(id=x.id, grade=x.grade, name=x.name) for x in q.order_by(Unit.grade, Unit.order)]


@app.post("/api/grader/problem", dependencies=[Depends(grader)])
async def g_problem(unit_id: int = Form(...), difficulty: str = Form(...), body: str = Form(""),
                    answer: str = Form(""), solution: str = Form(""), source: str = Form(""),
                    status: str = Form("draft"), job_id: int = Form(0),
                    image: UploadFile | None = File(None), sol_image: UploadFile | None = File(None),
                    db=Depends(get_db)):
    """문제 1개 등록 (PDF 자동 분류 결과 또는 Claude가 만든 묶음 업로드)."""
    if difficulty not in DIFFS or not db.get(Unit, unit_id):
        raise HTTPException(400, "unit/difficulty")
    p = Problem(unit_id=unit_id, difficulty=difficulty, body=body, answer=answer, solution=solution,
                source=source, status=status if status in ("draft", "published") else "draft",
                import_job_id=job_id or None)
    if image and image.filename:
        p.image_id = save_image(db, await image.read(), 2000)
    if sol_image and sol_image.filename:
        p.solution_image_id = save_image(db, await sol_image.read(), 2000)
    db.add(p)
    db.commit()
    return dict(id=p.id)


@app.post("/api/grader/import/{jid}", dependencies=[Depends(grader)])
async def g_import_done(jid: int, request: Request, db=Depends(get_db)):
    data = await request.json()
    j = db.get(ImportJob, jid)
    j.status = "error" if data.get("error") else "done"
    j.log = str(data.get("log", ""))[:5000]
    _seen(db)
    db.commit()
    return dict(ok=True)


@app.post("/api/grader/report/{rid}", dependencies=[Depends(grader)])
async def g_report(rid: int, request: Request, db=Depends(get_db)):
    data = await request.json()
    r = db.get(Report, rid)
    if data.get("error"):
        r.status = "error"  # 총평 없이 통계만 보여 준다 (선생님이 직접 써도 됨)
    else:
        r.ai_comment, r.status = str(data.get("comment", ""))[:3000], "done"
    _seen(db)
    db.commit()
    return dict(ok=True)


@app.get("/healthz")
def healthz():
    return JSONResponse({"ok": True})
