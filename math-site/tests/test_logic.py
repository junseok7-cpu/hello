import random
from datetime import timedelta

import pytest
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import db as D
from app import logic as L


@pytest.fixture()
def db():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    D.Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng, expire_on_commit=False)()
    from app.curriculum import seed_units
    seed_units(s)
    s.commit()
    yield s
    s.close()


def unit(db, grade, i=0):
    return db.query(D.Unit).filter_by(grade=grade).order_by(D.Unit.order).all()[i]


def prob(db, grade, diff, i=0):
    p = D.Problem(unit_id=unit(db, grade, i).id, difficulty=diff, body="x", status="published")
    db.add(p)
    db.flush()
    return p


def student(db, grade="중2"):
    u = D.User(name="s", grade=grade, discord_id=f"d{random.random()}")
    db.add(u)
    db.flush()
    return u


def submit(db, u, p, score):
    s = L.create_submission(db, u, p, [1])
    db.flush()
    L.apply_grade(db, s, score)
    db.flush()
    return s


def test_eligible_grade_rule():
    assert L.eligible("중2", "하", "중2")
    assert L.eligible("중1", "상", "중2")
    assert not L.eligible("중1", "중", "중2")
    assert not L.eligible("중3", "상", "중2")
    assert L.eligible("중1", "상", "고1")


def test_pool_respects_grade(db):
    u = student(db, "중2")
    ok = [prob(db, "중2", "하"), prob(db, "중2", "상"), prob(db, "중1", "상")]
    prob(db, "중1", "중")
    prob(db, "중3", "하")
    assert {p.id for p in L.fresh_pool(db, u)} == {p.id for p in ok}


def test_rewards_and_daily_cap(db):
    u = student(db)
    for _ in range(29):
        submit(db, u, prob(db, "중2", "중"), 95)
    assert L.balance(db, u.id) == 290
    s = submit(db, u, prob(db, "중2", "하"), 100)
    assert s.reward_amount == 10 and L.balance(db, u.id) == 300
    s = submit(db, u, prob(db, "중2", "중"), 100)
    assert s.reward_status == "capped" and L.balance(db, u.id) == 300


def test_hard_needs_approval_and_reserves_cap(db):
    u = student(db)
    s1 = submit(db, u, prob(db, "중2", "상"), 92)
    assert s1.reward_status == "pending" and L.balance(db, u.id) == 0
    s2 = submit(db, u, prob(db, "중2", "상"), 92)
    s3 = submit(db, u, prob(db, "중2", "상"), 92)
    s4 = submit(db, u, prob(db, "중2", "상"), 92)  # 300 이미 예약됨
    assert s4.reward_status == "capped"
    L.approve(db, s1)
    assert L.balance(db, u.id) == 100
    L.reject(db, s2, "풀이 비약")
    sp = L.get_sp(db, u.id, s2.problem_id)
    assert sp.state == "open" and sp.fail_count == 1
    L.approve(db, s3)
    assert L.balance(db, u.id) == 200


def test_three_fails_lock_then_half_reward(db):
    u = student(db)
    p = prob(db, "중2", "중")
    for _ in range(3):
        submit(db, u, p, 50)
    sp = L.get_sp(db, u.id, p.id)
    assert sp.state == "locked" and sp.solution_revealed
    assert not L.can_submit(db, u, p.id)
    sp.locked_until = D.now() - timedelta(seconds=1)
    assert L.can_submit(db, u, p.id) and sp in L.retry_list(db, u.id)
    s = submit(db, u, p, 95)
    assert s.is_retry and s.reward_amount == 5 and sp.state == "solved"


def test_weak_unit_detection(db):
    u = student(db)
    for i in range(20):
        submit(db, u, prob(db, "중2", "중", 0), 50 if i < 10 else 95)  # 오답률 50%
    for i in range(19):
        submit(db, u, prob(db, "중2", "중", 1), 50)  # 표본 부족
    weak = L.weak_units(db, u.id)
    assert unit(db, "중2", 0).id in weak and unit(db, "중2", 1).id not in weak


def test_weak_hard_threshold(db):
    u = student(db)
    for i in range(10):
        submit(db, u, prob(db, "중2", "상", 2), 50 if i < 7 else 95)
    assert unit(db, "중2", 2).id in L.weak_units(db, u.id)


def test_pick_prefers_weak(db):
    u = student(db)
    for i in range(20):
        submit(db, u, prob(db, "중2", "중", 0), 50)
    weak_new = [prob(db, "중2", "하", 0) for _ in range(5)]
    for _ in range(5):
        prob(db, "중2", "하", 3)
    rng = random.Random(1)
    hits = sum(L.pick_problem(db, u, rng).unit_id == weak_new[0].unit_id for _ in range(200))
    assert hits > 120  # 약 70% + 무작위로 뽑힌 몫


def test_appeal_accept_turns_fail_into_pass(db):
    u = student(db)
    p = prob(db, "중2", "하")
    s = submit(db, u, p, 70)
    s.appeal_status = "open"
    L.resolve_appeal(db, s, True, 95)
    sp = L.get_sp(db, u.id, p.id)
    assert sp.state == "solved" and L.balance(db, u.id) == 10


def test_skip_once_per_day(db):
    u = student(db)
    ps = [prob(db, "중2", "하") for _ in range(3)]
    first = L.current_problem(db, u)
    assert L.skip_problem(db, u, random.Random(0))
    assert u.current_problem_id != first.id
    assert not L.can_skip(u) and not L.skip_problem(db, u)


def test_report_period():
    from datetime import date
    from app.reports import latest_period, current_period
    assert latest_period(date(2026, 11, 28)) == ("2026-10-28", "2026-11-27")
    assert latest_period(date(2026, 11, 27)) == ("2026-09-28", "2026-10-27")
    assert latest_period(date(2026, 1, 5)) == ("2025-11-28", "2025-12-27")
    assert current_period(date(2026, 11, 28)) == ("2026-11-28", "2026-11-28")


def test_report_collect(db):
    import json
    from datetime import date
    from app import reports as R
    u = student(db)
    u.created_at = D.now() - timedelta(days=60)
    s1 = submit(db, u, prob(db, "중2", "중", 0), 95)
    s2 = submit(db, u, prob(db, "중2", "상", 1), 40)
    for s in (s1, s2):
        s.kst_date = "2026-11-10"
    db.query(D.Ledger).update({"kst_date": "2026-11-10"})
    assert R.ensure_reports(db, date(2026, 11, 28)) == 1
    assert R.ensure_reports(db, date(2026, 11, 29)) == 0  # 같은 기간은 한 번만
    d = json.loads(db.query(D.Report).one().data)
    assert d["submissions"] == 2 and d["passed"] == 1 and d["pass_rate"] == 50 and d["earned"] == 10
    assert d["by_diff"]["상"] == {"n": 1, "pass": 0}
