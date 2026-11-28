"""학습 규칙: 출제, 적립, 잠금, 취약단원. 웹·채점과 분리해 테스트하기 쉽게 둔다."""
import random
from datetime import timedelta

from sqlalchemy import func

from .db import (GRADES, Ledger, Problem, StudentProblem, Submission, Unit, User,
                 get_setting, kst_today, now)


def _f(db, key):
    return float(get_setting(db, key))


# ---------- 학년 범위 (요구사항 14) ----------

def eligible(problem_grade: str, difficulty: str, student_grade: str) -> bool:
    """자기 학년은 전 난이도, 아래 학년은 '상'만."""
    if problem_grade not in GRADES or student_grade not in GRADES:
        return False
    pg, sg = GRADES.index(problem_grade), GRADES.index(student_grade)
    return pg == sg or (pg < sg and difficulty == "상")


def eligible_units(db, student_grade):
    sg = GRADES.index(student_grade)
    return db.query(Unit).filter(Unit.grade.in_(GRADES[:sg + 1])).order_by(Unit.grade, Unit.order).all()


# ---------- 취약단원 (요구사항 10, 12, 13) ----------

def unit_stats(db, user_id):
    """단원별 {중: [채점수, 오답수], 상: [...], 하: [...]} — 채점된 모든 제출 기준."""
    rows = (db.query(Problem.unit_id, Problem.difficulty, Submission.score, Submission.reward_status)
            .join(Submission, Submission.problem_id == Problem.id)
            .filter(Submission.user_id == user_id, Submission.status == "graded").all())
    pass_score = int(get_setting(db, "pass_score"))
    stats = {}
    for unit_id, diff, score, rstatus in rows:
        s = stats.setdefault(unit_id, {"하": [0, 0], "중": [0, 0], "상": [0, 0]})
        s[diff][0] += 1
        wrong = score is None or score < pass_score or rstatus == "rejected"
        if wrong:
            s[diff][1] += 1
    return stats


def judge_unit(db, s):
    """'weak' | 'ok' | 'collecting'(표본 부족)."""
    mid_n, mid_w = s["중"]
    hi_n, hi_w = s["상"]
    ms, hs = int(get_setting(db, "mid_sample")), int(get_setting(db, "hi_sample"))
    mid_ready, hi_ready = mid_n >= ms, hi_n >= hs
    if mid_ready and mid_w / mid_n >= _f(db, "mid_wrong"):
        return "weak"
    if hi_ready and hi_w / hi_n >= _f(db, "hi_wrong"):
        return "weak"
    return "ok" if (mid_ready or hi_ready) else "collecting"


def weak_units(db, user_id):
    return [uid for uid, s in unit_stats(db, user_id).items() if judge_unit(db, s) == "weak"]


# ---------- 출제 (요구사항 11, 13, 14) ----------

def fresh_pool(db, user: User):
    """아직 손대지 않은 출제 가능 문제."""
    touched = db.query(StudentProblem.problem_id).filter(StudentProblem.user_id == user.id)
    sg = GRADES.index(user.grade)
    lower = GRADES[:sg]
    q = (db.query(Problem).join(Unit).filter(Problem.status == "published",
                                             ~Problem.id.in_(touched))
         .filter((Unit.grade == user.grade) | ((Unit.grade.in_(lower)) & (Problem.difficulty == "상"))))
    return q.all()


def pick_problem(db, user: User, rng=random):
    pool = fresh_pool(db, user)
    if not pool:
        return None
    weak = set(weak_units(db, user.id))
    weak_pool = [p for p in pool if p.unit_id in weak]
    if weak_pool and rng.random() < _f(db, "weak_ratio"):
        return rng.choice(weak_pool)
    return rng.choice(pool)


def current_problem(db, user: User):
    """지금 풀 문제. 없으면 새로 뽑아 고정 (새로고침으로 바꾸기 방지)."""
    if user.current_problem_id:
        p = db.get(Problem, user.current_problem_id)
        if p and p.status == "published":
            return p
    p = pick_problem(db, user)
    user.current_problem_id = p.id if p else None
    return p


def retry_list(db, user_id):
    """다시 도전 가능한 문제 (실패 후 open, 또는 잠금 기간이 끝난 문제)."""
    t = now()
    sps = db.query(StudentProblem).filter(StudentProblem.user_id == user_id,
                                          StudentProblem.state.in_(["open", "locked"])).all()
    out = []
    for sp in sps:
        if sp.state == "locked":
            if sp.locked_until and sp.locked_until <= t:
                out.append(sp)
        else:
            out.append(sp)
    return out


def can_submit(db, user: User, problem_id: int):
    if user.current_problem_id == problem_id:
        sp = get_sp(db, user.id, problem_id)
        return sp is None or sp.state == "open" or _lock_over(sp)
    sp = get_sp(db, user.id, problem_id)
    return sp is not None and (sp.state == "open" or _lock_over(sp))


def _lock_over(sp):
    return sp.state == "locked" and sp.locked_until and sp.locked_until <= now()


def get_sp(db, user_id, problem_id):
    return db.query(StudentProblem).filter_by(user_id=user_id, problem_id=problem_id).first()


def create_submission(db, user: User, problem: Problem, image_ids, typed_answer=""):
    sp = get_sp(db, user.id, problem.id)
    if sp is None:
        sp = StudentProblem(user_id=user.id, problem_id=problem.id, fail_count=0)
        db.add(sp)
    elif _lock_over(sp):  # 한 달 뒤 재도전 라운드 시작
        sp.fail_count = 0
        sp.is_retry = True
    sp.state = "waiting"
    sub = Submission(user_id=user.id, problem_id=problem.id,
                     image_ids=",".join(str(i) for i in image_ids),
                     typed_answer=typed_answer[:300], is_retry=bool(sp.is_retry),
                     kst_date=kst_today())
    db.add(sub)
    if user.current_problem_id == problem.id:
        user.current_problem_id = None
    db.flush()
    return sub


# ---------- 적립 (요구사항 3, 7, 9) ----------

def used_today(db, user_id, kst_date, exclude_sub_id=None):
    """그날 적립된 금액 + 승인 대기로 예약된 금액."""
    credited = (db.query(func.coalesce(func.sum(Ledger.amount), 0))
                .filter(Ledger.user_id == user_id, Ledger.kind == "reward",
                        Ledger.kst_date == kst_date).scalar())
    q = db.query(func.coalesce(func.sum(Submission.reward_amount), 0)).filter(
        Submission.user_id == user_id, Submission.kst_date == kst_date,
        Submission.reward_status == "pending")
    if exclude_sub_id:
        q = q.filter(Submission.id != exclude_sub_id)
    return int(credited) + int(q.scalar())


def balance(db, user_id):
    return int(db.query(func.coalesce(func.sum(Ledger.amount), 0))
               .filter(Ledger.user_id == user_id).scalar())


def reward_for(sub: Submission):
    base = sub.problem.reward
    return base // 2 if sub.is_retry else base


def _apply_pass(db, sub: Submission, sp: StudentProblem):
    cap = int(get_setting(db, "daily_cap"))
    room = max(0, cap - used_today(db, sub.user_id, sub.kst_date, exclude_sub_id=sub.id))
    amount = min(reward_for(sub), room)
    sub.reward_amount = amount
    if sub.problem.difficulty == "상" and amount > 0:
        sub.reward_status = "pending"  # 선생님 승인 후 적립
        sp.state = "pending"
        return
    if amount > 0:
        sub.reward_status = "credited"
        db.add(Ledger(user_id=sub.user_id, amount=amount, kind="reward",
                      submission_id=sub.id, kst_date=sub.kst_date,
                      memo=f"#{sub.problem_id} {sub.problem.difficulty}" + (" 재도전" if sub.is_retry else "")))
    else:
        sub.reward_status = "capped"
    sp.state = "solved"


def _apply_fail(db, sp: StudentProblem):
    sp.fail_count += 1
    if sp.fail_count >= int(get_setting(db, "max_fails")):
        sp.state = "locked"
        sp.solution_revealed = True
        sp.locked_until = now() + timedelta(days=int(get_setting(db, "lock_days")))
    else:
        sp.state = "open"


def apply_grade(db, sub: Submission, score: int, feedback="", answer_read="", engine="", errors=""):
    sub.ai_errors = errors
    sub.score = max(0, min(100, int(score)))
    sub.feedback, sub.answer_read, sub.engine = feedback, answer_read[:300], engine
    sub.status, sub.graded_at = "graded", now()
    sp = get_sp(db, sub.user_id, sub.problem_id)
    if sub.score >= int(get_setting(db, "pass_score")):
        _apply_pass(db, sub, sp)
    else:
        _apply_fail(db, sp)


def approve(db, sub: Submission):
    """상 문제 승인 → 적립."""
    if sub.reward_status != "pending":
        return
    sp = get_sp(db, sub.user_id, sub.problem_id)
    sub.reward_status = "credited"
    db.add(Ledger(user_id=sub.user_id, amount=sub.reward_amount, kind="reward",
                  submission_id=sub.id, kst_date=sub.kst_date,
                  memo=f"#{sub.problem_id} 상 승인" + (" 재도전" if sub.is_retry else "")))
    sp.state = "solved"


def reject(db, sub: Submission, note=""):
    """상 문제 반려 → 오답 1회로 처리."""
    if sub.reward_status != "pending":
        return
    sp = get_sp(db, sub.user_id, sub.problem_id)
    sub.reward_status, sub.reward_amount, sub.teacher_note = "rejected", 0, note
    _apply_fail(db, sp)


def resolve_appeal(db, sub: Submission, accept: bool, new_score=None, note=""):
    """이의신청 처리 (요구사항 15). 인정 + 통과 점수면 실패 1회를 되돌리고 통과 처리."""
    sub.teacher_note = note
    if not accept:
        sub.appeal_status = "rejected"
        return
    sub.appeal_status = "accepted"
    if new_score is None:
        return
    was_pass = sub.passed
    sub.score = max(0, min(100, int(new_score)))
    sp = get_sp(db, sub.user_id, sub.problem_id)
    if not was_pass and sub.passed and sp.state in ("open", "locked", "waiting"):
        sp.fail_count = max(0, sp.fail_count - 1)
        sp.locked_until = None
        _apply_pass(db, sub, sp)
