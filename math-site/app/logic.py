"""학습 규칙: 출제, 적립, 잠금, 취약단원. 웹·채점과 분리해 테스트하기 쉽게 둔다."""
import random
from datetime import timedelta

from sqlalchemy import func, update

from .db import (DIFFS, GRADES, Ledger, Problem, StudentProblem, Submission, Unit, User,
                 get_setting, kst_today, now)


def _f(db, key):
    return float(get_setting(db, key))


# ---------- 과목별 규칙 ----------
# math: 하·중 10원 / 상 100원, 아래 학년은 '상'만
# science: 모든 문제 20원(설정 reward_science), 아래 학년 안 냄, 하→중→상 돌아가며 섞어 냄
RULES = {
    "math": dict(cap="cap_math", lower_grades="상", mix=False,
                 cur="current_problem_id", skip="skip_date"),
    "science": dict(cap="cap_science", lower_grades=None, mix=True,
                    cur="current_sci_id", skip="skip_date_sci"),
}


def subject_of(p: Problem) -> str:
    return p.unit.subject if p.unit else "math"


def base_reward(db, p: Problem) -> int:
    if subject_of(p) == "science":
        return int(get_setting(db, "reward_science"))
    return 100 if p.difficulty == "상" else 10


# ---------- 학년 범위 (요구사항 14) ----------

def eligible(problem_grade: str, difficulty: str, student_grade: str, subject="math") -> bool:
    """수학: 자기 학년 전 난이도 + 아래 학년 '상'만. 과학: 자기 학년만."""
    if problem_grade not in GRADES or student_grade not in GRADES:
        return False
    pg, sg = GRADES.index(problem_grade), GRADES.index(student_grade)
    lower = RULES[subject]["lower_grades"]
    return pg == sg or (pg < sg and lower is not None and difficulty == lower)


def eligible_units(db, student_grade, subject="math"):
    sg = GRADES.index(student_grade)
    grades = GRADES[:sg + 1] if RULES[subject]["lower_grades"] else [student_grade]
    return (db.query(Unit).filter(Unit.subject == subject, Unit.grade.in_(grades))
            .order_by(Unit.grade, Unit.order).all())


# ---------- 취약단원 (요구사항 10, 12, 13) ----------

def unit_stats(db, user_id, subject=None):
    """단원별 {중: [채점수, 오답수], 상: [...], 하: [...]} — 채점된 문제 기준."""
    q = (db.query(Problem.id, Problem.unit_id, Problem.difficulty, Submission.score, Submission.reward_status)
         .join(Submission, Submission.problem_id == Problem.id)
         .filter(Submission.user_id == user_id, Submission.status == "graded",
                 Submission.reward_status != "pending"))
    if subject:
        q = q.join(Unit, Unit.id == Problem.unit_id).filter(Unit.subject == subject)
    rows = q.all()
    pass_score = int(get_setting(db, "pass_score"))
    problems, wrong = {}, set()
    for pid, unit_id, diff, score, rstatus in rows:
        problems[pid] = (unit_id, diff)
        if score is None or score < pass_score or rstatus == "rejected":
            wrong.add(pid)
    stats = {}
    for pid, (unit_id, diff) in problems.items():
        s = stats.setdefault(unit_id, {"하": [0, 0], "중": [0, 0], "상": [0, 0]})
        s[diff][0] += 1
        if pid in wrong:
            s[diff][1] += 1
    return stats


def judge_unit(db, s):
    """'weak' | 'ok' | 'collecting'(표본 부족)."""
    mid_n, mid_w = s["중"]
    hi_n, hi_w = s["상"]
    ms, hs = int(get_setting(db, "mid_sample")), int(get_setting(db, "hi_sample"))
    mid_ready, hi_ready = mid_n > 0 and mid_n >= ms, hi_n > 0 and hi_n >= hs
    if mid_ready and mid_w / mid_n >= _f(db, "mid_wrong"):
        return "weak"
    if hi_ready and hi_w / hi_n >= _f(db, "hi_wrong"):
        return "weak"
    return "ok" if (mid_ready or hi_ready) else "collecting"


def weak_units(db, user_id, subject=None):
    return [uid for uid, s in unit_stats(db, user_id, subject).items() if judge_unit(db, s) == "weak"]


# ---------- 출제 (요구사항 11, 13, 14) ----------

def fresh_pool(db, user: User, subject="math"):
    """아직 손대지 않은 출제 가능 문제."""
    touched = db.query(StudentProblem.problem_id).filter(StudentProblem.user_id == user.id)
    sg = GRADES.index(user.grade)
    lower = GRADES[:sg]
    q = (db.query(Problem).join(Unit).filter(Problem.status == "published", Unit.subject == subject,
                                             ~Problem.id.in_(touched)))
    lower_diff = RULES[subject]["lower_grades"]
    if lower_diff:
        q = q.filter((Unit.grade == user.grade) | ((Unit.grade.in_(lower)) & (Problem.difficulty == lower_diff)))
    else:
        q = q.filter(Unit.grade == user.grade)
    return q.all()


def _next_diff(db, user: User, subject):
    """섞어 내기: 이 과목에서 받은 문제 수에 따라 하 → 중 → 상 → 하 ..."""
    n = (db.query(StudentProblem).join(Problem).join(Unit)
         .filter(StudentProblem.user_id == user.id, Unit.subject == subject).count())
    return DIFFS[n % 3]


def pick_problem(db, user: User, subject="math", rng=random, exclude=None):
    pool = [p for p in fresh_pool(db, user, subject) if p.id != exclude]
    if not pool:
        return None
    if RULES[subject]["mix"]:
        target = _next_diff(db, user, subject)
        same = [p for p in pool if p.difficulty == target]
        pool = same or pool  # 그 난이도가 다 떨어졌으면 남은 것에서
    weak = set(weak_units(db, user.id, subject))
    weak_pool = [p for p in pool if p.unit_id in weak]
    if weak_pool and rng.random() < _f(db, "weak_ratio"):
        return rng.choice(weak_pool)
    return rng.choice(pool)


def current_problem(db, user: User, subject="math"):
    """지금 풀 문제. 없으면 새로 뽑아 고정 (새로고침으로 바꾸기 방지)."""
    attr = RULES[subject]["cur"]
    pid = getattr(user, attr)
    if pid:
        p = db.get(Problem, pid)
        if p and p.status == "published":
            return p
    p = pick_problem(db, user, subject)
    setattr(user, attr, p.id if p else None)
    return p


def can_skip(user: User, subject="math"):
    return getattr(user, RULES[subject]["skip"]) != kst_today()


def skip_problem(db, user: User, subject="math", rng=random):
    """오늘의 문제 건너뛰기 (과목마다 하루 1번). 건너뛴 문제는 나중에 다시 나올 수 있다."""
    r = RULES[subject]
    cur = getattr(user, r["cur"])
    if not can_skip(user, subject) or not cur:
        return False
    new = pick_problem(db, user, subject, rng, exclude=cur)
    if new is None:
        return False
    setattr(user, r["cur"], new.id)
    setattr(user, r["skip"], kst_today())
    return True


def is_current(user: User, problem_id):
    return problem_id in (user.current_problem_id, user.current_sci_id)


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
    p = db.get(Problem, problem_id)
    if not p or p.status != "published" or not eligible(p.grade, p.difficulty, user.grade, p.subject):
        return False
    if is_current(user, problem_id):
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
    else:
        if not _claim_result(db, sp, ("open", "locked")):
            raise ValueError("지금은 이 문제를 제출할 수 없어요")
        db.refresh(sp)
        if _lock_over(sp):
            sp.fail_count = 0
            sp.is_retry = True
        elif sp.state != "open":
            raise ValueError("지금은 이 문제를 제출할 수 없어요")
    sp.state = "waiting"
    sub = Submission(user_id=user.id, problem_id=problem.id,
                     image_ids=",".join(str(i) for i in image_ids),
                     typed_answer=typed_answer[:300], is_retry=bool(sp.is_retry),
                     kst_date=kst_today())
    db.add(sub)
    for r in RULES.values():
        if getattr(user, r["cur"]) == problem.id:
            setattr(user, r["cur"], None)
    db.flush()
    return sub


# ---------- 적립 (요구사항 3, 7, 9) ----------

def used_today(db, user_id, kst_date, subject="math", exclude_sub_id=None):
    """그날 그 과목에서 적립된 금액 + 승인 대기로 예약된 금액."""
    credited = (db.query(func.coalesce(func.sum(Ledger.amount), 0))
                .join(Submission, Submission.id == Ledger.submission_id)
                .join(Problem, Problem.id == Submission.problem_id).join(Unit, Unit.id == Problem.unit_id)
                .filter(Ledger.user_id == user_id, Ledger.kind == "reward",
                        Ledger.kst_date == kst_date, Unit.subject == subject).scalar())
    q = (db.query(func.coalesce(func.sum(Submission.reward_amount), 0))
         .join(Problem, Problem.id == Submission.problem_id).join(Unit, Unit.id == Problem.unit_id)
         .filter(Submission.user_id == user_id, Submission.kst_date == kst_date,
                 Submission.reward_status == "pending", Unit.subject == subject))
    if exclude_sub_id:
        q = q.filter(Submission.id != exclude_sub_id)
    return int(credited) + int(q.scalar())


def cap_of(db, subject):
    return int(get_setting(db, RULES[subject]["cap"]))


def balance(db, user_id):
    return int(db.query(func.coalesce(func.sum(Ledger.amount), 0))
               .filter(Ledger.user_id == user_id).scalar())


def reward_for(db, sub: Submission):
    base = base_reward(db, sub.problem)
    return base // 2 if sub.is_retry else base


def _credit(db, sub, memo):
    if sub.reward_amount > 0 and not db.query(Ledger).filter_by(submission_id=sub.id).first():
        db.add(Ledger(user_id=sub.user_id, amount=sub.reward_amount, kind="reward",
                      submission_id=sub.id, kst_date=sub.kst_date,
                      memo=memo + (" 재도전" if sub.is_retry else "")))


def _apply_pass(db, sub: Submission, sp: StudentProblem):
    subj = subject_of(sub.problem)
    room = max(0, cap_of(db, subj) - used_today(db, sub.user_id, sub.kst_date, subj, exclude_sub_id=sub.id))
    amount = min(reward_for(db, sub), room)
    sub.reward_amount = amount
    if sub.problem.difficulty == "상":
        sub.reward_status = "pending"  # 선생님 승인 후 적립
        sp.state = "pending"
        sp.solution_revealed = False
        return
    if amount > 0:
        sub.reward_status = "credited"
        _credit(db, sub, f"#{sub.problem_id} {sub.problem.difficulty}")
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
    if not _claim_result(db, sp):
        sub.reward_status = "none"
        sub.feedback = (sub.feedback + "\n이미 해결한 문제라 적립 없음").strip()
        return
    db.refresh(sp)
    if sub.score >= int(get_setting(db, "pass_score")):
        _apply_pass(db, sub, sp)
    else:
        _apply_fail(db, sp)


def _claim_result(db, sp, states=("waiting", "open", "locked")):
    # 진행 상태를 바꾸기 전에 행을 먼저 확보한다.
    return db.execute(update(StudentProblem).where(
        StudentProblem.id == sp.id, StudentProblem.state.in_(states)
    ).values(state=StudentProblem.state).execution_options(synchronize_session=False)).rowcount


def _take_pending(db, sub, status):
    if sub.reward_status != "pending":
        return False
    changed = db.execute(update(Submission).where(
        Submission.id == sub.id, Submission.reward_status == "pending"
    ).values(reward_status=status).execution_options(synchronize_session=False)).rowcount
    if changed:
        db.refresh(sub)
    return changed


def approve(db, sub: Submission):
    """상 문제 승인 → 적립."""
    if not _take_pending(db, sub, "credited"):
        return
    sp = get_sp(db, sub.user_id, sub.problem_id)
    _credit(db, sub, f"#{sub.problem_id} 상 승인")
    sp.state = "solved"


def reject(db, sub: Submission, note=""):
    """상 문제 반려 → 오답 1회로 처리."""
    if not _take_pending(db, sub, "rejected"):
        return
    sp = get_sp(db, sub.user_id, sub.problem_id)
    amount = sub.reward_amount
    sub.reward_amount, sub.teacher_note = 0, note
    _apply_fail(db, sp)
    if amount <= 0:
        return
    subject = sub.problem.subject
    capped = (db.query(Submission).join(Problem).join(Unit)
              .filter(Submission.user_id == sub.user_id, Submission.kst_date == sub.kst_date,
                      Unit.subject == subject, Submission.status == "graded",
                      (Submission.reward_status == "capped") |
                      ((Submission.reward_status == "pending") & (Submission.reward_amount == 0)))
              .order_by(Submission.id))
    for other in capped:
        if used_today(db, sub.user_id, sub.kst_date, subject) >= cap_of(db, subject):
            break
        if db.execute(update(Submission).where(
            Submission.id == other.id, Submission.reward_status == other.reward_status,
            Submission.reward_amount == 0
        ).values(reward_amount=0).execution_options(synchronize_session=False)).rowcount:
            _apply_pass(db, other, get_sp(db, other.user_id, other.problem_id))


def resolve_appeal(db, sub: Submission, accept: bool, new_score=None, note=""):
    """통과한 이의신청은 오답 한 번을 되돌린다."""
    if sub.appeal_status != "open":
        return
    if accept and (type(new_score) is not int or not 0 <= new_score <= 100):
        raise ValueError("새 점수는 0~100 정수로 입력해 주세요")
    status = "accepted" if accept else "rejected"
    if not db.execute(update(Submission).where(
        Submission.id == sub.id, Submission.appeal_status == "open"
    ).values(appeal_status=status).execution_options(synchronize_session=False)).rowcount:
        return
    sub.teacher_note, sub.appeal_status = note, status
    if not accept:
        return
    threshold = int(get_setting(db, "pass_score"))
    was_wrong = sub.score is None or sub.score < threshold or sub.reward_status == "rejected"
    sub.score = new_score
    if was_wrong and new_score >= threshold:
        sp = get_sp(db, sub.user_id, sub.problem_id)
        if _claim_result(db, sp, ("open", "locked", "waiting", "pending", "solved")):
            db.refresh(sp)
            sp.fail_count = max(0, sp.fail_count - 1)
            if sp.state in ("pending", "solved"):
                sub.reward_status = "none"
                return
            sp.locked_until = None
            _apply_pass(db, sub, sp)
