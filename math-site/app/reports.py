"""월간 보고서: 매월 28일에 '전월 28일 ~ 이번 달 27일' 학생별 기록을 모은다.

사이트가 잠들어 있어도 되도록, 채점 PC가 일을 가져갈 때와 선생님이 대시보드를 열 때
'만들 차례인 보고서'가 있는지 확인해서 만든다. AI 총평은 채점 PC가 나중에 채운다.
"""
import json
from datetime import date, datetime, timedelta

from sqlalchemy import func

from . import logic
from .db import KST, Ledger, Report, Submission, Unit, User, get_setting


def _d(s):
    return date.fromisoformat(s)


def latest_period(today: date):
    """오늘 기준으로 이미 끝난 가장 최근 보고 기간 (start, end)."""
    y, m = today.year, today.month
    if today.day < 28:  # 이번 달 28일 전 → 지난달 보고서가 최신
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    end = date(y, m, 27)
    pm, py = (m - 1, y) if m > 1 else (12, y - 1)
    start = date(py, pm, 28)
    return start.isoformat(), end.isoformat()


def current_period(today: date):
    """진행 중인 기간 (미리보기용)."""
    _, e = latest_period(today)
    return (_d(e) + timedelta(days=1)).isoformat(), today.isoformat()


def today_kst():
    return datetime.now(KST).date()


def collect(db, user: User, start: str, end: str) -> dict:
    pass_score = int(get_setting(db, "pass_score"))
    subs = (db.query(Submission).filter(Submission.user_id == user.id,
                                        Submission.kst_date >= start, Submission.kst_date <= end)
            .order_by(Submission.id).all())
    graded = [s for s in subs if s.status == "graded"]

    def ok(s):
        return s.score is not None and s.score >= pass_score and s.reward_status != "rejected"

    by_diff = {d: {"n": 0, "pass": 0} for d in ("하", "중", "상")}
    by_unit = {}
    for s in graded:
        d = s.problem.difficulty
        by_diff[d]["n"] += 1
        by_diff[d]["pass"] += ok(s)
        u = by_unit.setdefault(s.problem.unit_id, {"name": f"{s.problem.unit.grade} {s.problem.unit.name}",
                                                    "n": 0, "pass": 0})
        u["n"] += 1
        u["pass"] += ok(s)
    units = sorted(by_unit.values(), key=lambda x: (-(x["n"] - x["pass"]) / max(1, x["n"]), -x["n"]))

    def ledger_sum(kind):
        return int(db.query(func.coalesce(func.sum(Ledger.amount), 0)).filter(
            Ledger.user_id == user.id, Ledger.kind == kind,
            Ledger.kst_date >= start, Ledger.kst_date <= end).scalar())

    passed = sum(ok(s) for s in graded)
    prev = (db.query(Report).filter(Report.user_id == user.id, Report.period_end < end)
            .order_by(Report.period_end.desc()).first())
    prev_rate = json.loads(prev.data).get("pass_rate") if prev else None
    return dict(
        name=user.name, grade=user.grade, start=start, end=end,
        submissions=len(subs), graded=len(graded), passed=passed,
        pass_rate=round(passed * 100 / len(graded)) if graded else None,
        prev_pass_rate=prev_rate,
        active_days=len({s.kst_date for s in subs}),
        retry_pass=sum(1 for s in graded if s.is_retry and ok(s)),
        by_diff=by_diff, units=units,
        earned=ledger_sum("reward"), paid=-ledger_sum("payout"), balance=logic.balance(db, user.id),
        capped_days=len({s.kst_date for s in subs if s.reward_status == "capped"}),
        appeals=sum(1 for s in subs if s.appeal_status != "none"),
        appeals_accepted=sum(1 for s in subs if s.appeal_status == "accepted"),
        weak_units=[f"{x.grade} {x.name}" for x in
                    (db.get(Unit, i) for i in logic.weak_units(db, user.id)) if x],
    )


def ensure_reports(db, today: date | None = None) -> int:
    """만들 차례인 보고서가 있으면 만든다. 새로 만든 개수를 돌려준다."""
    start, end = latest_period(today or today_kst())
    made = 0
    for u in db.query(User).filter(User.role == "student", User.active.is_(True),
                                   User.grade.isnot(None)).all():
        if u.created_at and (u.created_at + timedelta(hours=9)).date().isoformat() > end:
            continue  # 기간이 끝난 뒤에 등록된 학생
        if db.query(Report).filter_by(user_id=u.id, period_end=end).first():
            continue
        db.add(Report(user_id=u.id, period_start=start, period_end=end,
                      data=json.dumps(collect(db, u, start, end), ensure_ascii=False)))
        made += 1
    if made:
        db.flush()
    return made
