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


def unit(db, grade, i=0, subject="math"):
    return db.query(D.Unit).filter_by(grade=grade, subject=subject).order_by(D.Unit.order).all()[i]


def prob(db, grade, diff, i=0, subject="math"):
    p = D.Problem(unit_id=unit(db, grade, i, subject).id, difficulty=diff, body="x", status="published")
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
    assert (s4.reward_status, s4.reward_amount) == ("pending", 0)
    assert L.get_sp(db, u.id, s4.problem_id).state == "pending"
    L.approve(db, s1)
    assert L.balance(db, u.id) == 100
    L.reject(db, s2, "풀이 비약")
    sp = L.get_sp(db, u.id, s2.problem_id)
    assert sp.state == "open" and sp.fail_count == 1
    assert (s4.reward_status, s4.reward_amount) == ("pending", 100)
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
    subs = [submit(db, u, prob(db, "중2", "상", 2), 50 if i < 7 else 95) for i in range(10)]
    uid = unit(db, "중2", 2).id
    assert L.unit_stats(db, u.id)[uid]["상"] == [7, 7]
    assert uid not in L.weak_units(db, u.id)
    for sub in subs[7:]:
        L.approve(db, sub)
    assert L.unit_stats(db, u.id)[uid]["상"] == [10, 7]
    assert uid in L.weak_units(db, u.id)


def test_pick_prefers_weak(db):
    u = student(db)
    for i in range(20):
        submit(db, u, prob(db, "중2", "중", 0), 50)
    weak_new = [prob(db, "중2", "하", 0) for _ in range(5)]
    for _ in range(5):
        prob(db, "중2", "하", 3)
    rng = random.Random(1)
    hits = sum(L.pick_problem(db, u, rng=rng).unit_id == weak_new[0].unit_id for _ in range(200))
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
    assert L.skip_problem(db, u, rng=random.Random(0))
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
    from datetime import date, datetime
    from app import reports as R
    u = student(db)
    u.created_at = datetime(2026, 11, 1)
    s1 = submit(db, u, prob(db, "중2", "중", 0), 95)
    s2 = submit(db, u, prob(db, "중2", "상", 1), 40)
    for s in (s1, s2):
        s.kst_date = "2026-11-10"
    db.query(D.Ledger).update({"kst_date": "2026-11-10"})
    assert R.ensure_reports(db, date(2026, 11, 28)) == 1
    assert R.ensure_reports(db, date(2026, 11, 29)) == 0  # 같은 기간은 한 번만
    d = json.loads(db.query(D.Report).one().data)
    m = d["subjects"]["math"]
    assert m["submissions"] == 2 and m["passed"] == 1 and m["pass_rate"] == 50 and m["earned"] == 10
    assert m["by_diff"]["상"] == {"n": 1, "pass": 0}
    assert d["subjects"]["science"]["submissions"] == 0 and d["earned"] == 10


# ---------- 과학 ----------

def test_science_reward_and_separate_cap(db):
    u = student(db)
    for _ in range(10):
        s = submit(db, u, prob(db, "중2", "하", subject="science"), 95)
    assert s.reward_amount == 20 and L.balance(db, u.id) == 200
    s = submit(db, u, prob(db, "중2", "중", subject="science"), 95)
    assert s.reward_status == "capped"  # 과학 200원 한도
    s = submit(db, u, prob(db, "중2", "중"), 95)
    assert s.reward_amount == 10  # 수학 한도는 따로
    assert L.used_today(db, u.id, D.kst_today(), "math") == 10


def test_science_no_lower_grade(db):
    u = student(db, "중2")
    own = prob(db, "중2", "상", subject="science")
    prob(db, "중1", "상", subject="science")
    assert [p.id for p in L.fresh_pool(db, u, "science")] == [own.id]
    assert all(p.subject == "math" for p in L.fresh_pool(db, u, "math"))


def test_science_mixes_difficulty(db):
    u = student(db, "중2")
    for d in "하중상" * 3:
        prob(db, "중2", d, subject="science")
    got = []
    for _ in range(6):
        p = L.current_problem(db, u, "science")
        got.append(p.difficulty)
        submit(db, u, p, 95)
    assert got == list("하중상하중상")


def test_science_hard_retry_half(db):
    u = student(db)
    p = prob(db, "중2", "중", subject="science")
    for _ in range(3):
        submit(db, u, p, 30)
    L.get_sp(db, u.id, p.id).locked_until = D.now() - timedelta(seconds=1)
    s = submit(db, u, p, 95)
    assert s.reward_amount == 10


def test_current_problem_per_subject(db):
    u = student(db)
    m = prob(db, "중2", "중")
    sc = prob(db, "중2", "하", subject="science")
    assert L.current_problem(db, u, "math").id == m.id
    assert L.current_problem(db, u, "science").id == sc.id
    assert L.can_submit(db, u, m.id) and L.can_submit(db, u, sc.id)


@pytest.mark.parametrize("difficulty", ["하", "상"])
def test_appeal_and_waiting_grade_credit_once(db, difficulty):
    u = student(db)
    p = prob(db, u.grade, difficulty)
    first = submit(db, u, p, 60)
    first.appeal_status = "open"
    retry = L.create_submission(db, u, p, [])
    L.resolve_appeal(db, first, True, 95)
    sp = L.get_sp(db, u.id, p.id)
    assert sp.fail_count == 0
    assert sp.state == ("pending" if difficulty == "상" else "solved")
    L.apply_grade(db, retry, 99, "풀이 확인")
    assert (retry.score, retry.status, retry.reward_status) == (99, "graded", "none")
    assert retry.feedback.endswith("이미 해결한 문제라 적립 없음")
    L.approve(db, first)
    L.approve(db, first)
    L.reject(db, first)
    assert sp.state == "solved" and sp.fail_count == 0
    assert db.query(D.Ledger.submission_id).all() == [(first.id,)]


def test_rejected_appeal_uses_configured_pass_score(db):
    u = student(db)
    D.set_setting(db, "pass_score", "80")
    sub = submit(db, u, prob(db, u.grade, "상"), 82)
    sp = L.get_sp(db, u.id, sub.problem_id)
    L.reject(db, sub, "반려")
    L.resolve_appeal(db, sub, True, 84)
    assert (sub.appeal_status, sub.teacher_note, sub.score) == ("none", "반려", 82)
    sub.appeal_status = "open"
    L.resolve_appeal(db, sub, True, 84)
    assert (sub.appeal_status, sub.reward_status, sp.state, sp.fail_count) == ("accepted", "pending", "pending", 0)
    L.resolve_appeal(db, sub, False, note="다시 처리")
    assert sub.appeal_status == "accepted" and sub.teacher_note == ""


def test_reward_submission_unique_and_manual_ledger_allows_null(db):
    from sqlalchemy.exc import IntegrityError
    u = student(db)
    sub = submit(db, u, prob(db, u.grade, "하"), 95)
    db.add_all([D.Ledger(user_id=u.id, amount=-1, kind="payout") for _ in range(2)])
    db.flush()
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(D.Ledger(user_id=u.id, amount=10, submission_id=sub.id))
        db.flush()
    assert L.balance(db, u.id) == 8


def test_reject_resettles_same_student_subject_and_day_in_order(db):
    u, other = student(db), student(db)
    D.set_setting(db, "cap_math", "15")
    D.set_setting(db, "cap_science", "0")
    reserved = submit(db, u, prob(db, u.grade, "상"), 90)
    next_day = submit(db, u, prob(db, u.grade, "하"), 90)
    next_day.kst_date = "2000-01-01"
    first, second, third = [submit(db, u, prob(db, u.grade, "하"), 90) for _ in range(3)]
    science = submit(db, u, prob(db, u.grade, "하", subject="science"), 90)
    other_reserved = submit(db, other, prob(db, u.grade, "상"), 90)
    other_capped = submit(db, other, prob(db, u.grade, "하"), 90)
    L.reject(db, reserved)
    assert [(s.reward_status, s.reward_amount) for s in (first, second, third)] == [
        ("credited", 10), ("credited", 5), ("capped", 0)]
    assert all(s.reward_status == "capped" for s in (next_day, science, other_capped))
    assert other_reserved.reward_amount == 15
    L.reject(db, reserved)
    assert L.balance(db, u.id) == 15


def test_zero_reward_hard_approval_solves_without_ledger(db):
    u = student(db)
    D.set_setting(db, "cap_math", "0")
    s = submit(db, u, prob(db, u.grade, "상"), 99)
    sp = L.get_sp(db, u.id, s.problem_id)
    assert (s.reward_status, s.reward_amount, sp.state, sp.solution_revealed) == ("pending", 0, "pending", False)
    L.approve(db, s)
    assert sp.state == "solved" and db.query(D.Ledger).count() == 0


def test_can_submit_checks_publication_scope_and_waiting(db):
    u = student(db)
    p = prob(db, u.grade, "하")
    u.current_problem_id = p.id
    assert L.can_submit(db, u, p.id)
    p.status = "draft"
    assert not L.can_submit(db, u, p.id)
    p.status = "published"
    L.create_submission(db, u, p, [])
    assert not L.can_submit(db, u, p.id)
    sc = prob(db, "중1", "상", subject="science")
    u.current_sci_id = sc.id
    assert not L.can_submit(db, u, sc.id)


def test_unit_stats_deduplicate_and_keep_any_wrong_attempt(db):
    u = student(db)
    p = prob(db, u.grade, "중")
    submit(db, u, p, 50)
    submit(db, u, p, 75)
    submit(db, u, p, 95)
    L.create_submission(db, u, prob(db, u.grade, "중"), [])
    s = submit(db, u, prob(db, u.grade, "상"), 90)
    submit(db, u, prob(db, u.grade, "상"), 90)
    L.reject(db, s)
    assert L.unit_stats(db, u.id)[p.unit_id] == {"하": [0, 0], "중": [1, 1], "상": [1, 1]}


def test_reports_fill_missing_periods_oldest_first(db):
    import json
    from datetime import date, datetime
    from app import reports as R

    u = student(db)
    u.created_at = datetime(2025, 12, 28)
    db.add(D.Report(user_id=u.id, period_start="2025-11-28", period_end="2025-12-27"))
    sub = submit(db, u, prob(db, u.grade, "하"), 92)
    sub.kst_date = "2026-01-10"
    assert R.ensure_reports(db, date(2026, 3, 28)) == 3
    reports = db.query(D.Report).order_by(D.Report.id).all()
    assert [r.period_end for r in reports] == ["2025-12-27", "2026-01-27", "2026-02-27", "2026-03-27"]
    assert json.loads(reports[2].data)["subjects"]["math"]["prev_pass_rate"] == 100
    assert R.ensure_reports(db, date(2026, 3, 28)) == 0


def test_reports_start_with_student_first_period(db):
    from datetime import date, datetime
    from app import reports as R

    u = student(db)
    u.created_at = datetime(2026, 1, 28)
    assert R.ensure_reports(db, date(2026, 3, 28)) == 2
    assert db.query(D.Report.period_end).order_by(D.Report.period_end).all() == [
        ("2026-02-27",), ("2026-03-27",)]


def test_report_duplicate_does_not_prevent_later_period(db, monkeypatch):
    from datetime import date, datetime
    from app import reports as R

    u = student(db)
    u.created_at = datetime(2026, 1, 1)
    original = R.collect

    def collect_with_conflict(db, user, start, end):
        if end == "2026-01-27":
            db.add(D.Report(user_id=user.id, period_start=start, period_end=end))
            db.flush()
        return original(db, user, start, end)

    monkeypatch.setattr(R, "collect", collect_with_conflict)
    assert R.ensure_reports(db, date(2026, 2, 28)) == 1
    assert db.query(D.Report.period_end).one() == ("2026-02-27",)


@pytest.mark.parametrize("duplicate_ledger", [False, True])
def test_startup_migrates_legacy_sqlite(db, monkeypatch, duplicate_ledger):
    from sqlalchemy import inspect, text

    u = student(db)
    sub = submit(db, u, prob(db, u.grade, "하"), 95)
    db.commit()
    eng = db.get_bind()
    with eng.begin() as conn:
        conn.execute(text("DROP INDEX uq_ledger_submission"))
        conn.execute(text("ALTER TABLE submissions DROP COLUMN retry_count"))
        if duplicate_ledger:
            conn.execute(text(
                "INSERT INTO ledger (user_id, amount, submission_id) VALUES (:uid, 10, :sid)"
            ), {"uid": u.id, "sid": sub.id})
    monkeypatch.setattr(D, "engine", eng)
    monkeypatch.setattr(D, "SessionLocal", sessionmaker(bind=eng))
    D.init_db()
    assert any(c["name"] == "retry_count" for c in inspect(eng).get_columns("submissions"))
    assert db.execute(text("SELECT retry_count FROM submissions")).scalar_one() == 0
    assert bool(inspect(eng).get_indexes("ledger")) == (not duplicate_ledger)
    assert db.query(D.Ledger).count() == (2 if duplicate_ledger else 1)


def test_appeal_winning_before_resubmission_cannot_reopen_problem(db):
    u = student(db)
    p = prob(db, u.grade, "하")
    first = submit(db, u, p, 40)
    assert L.can_submit(db, u, p.id)
    first.appeal_status = "open"
    L.resolve_appeal(db, first, True, 95)
    with pytest.raises(ValueError):
        L.create_submission(db, u, p, [])
    assert L.get_sp(db, u.id, p.id).state == "solved"
    assert db.query(D.Submission).count() == 1 and L.balance(db, u.id) == 10


def test_passing_grade_before_appeal_does_not_credit_twice(db):
    u = student(db)
    p = prob(db, u.grade, "하")
    first = submit(db, u, p, 50)
    first.appeal_status = "open"
    second = submit(db, u, p, 95)
    L.resolve_appeal(db, first, True, 91)
    assert (first.appeal_status, first.score, first.reward_status) == ("accepted", 91, "none")
    assert L.get_sp(db, u.id, p.id).fail_count == 0
    assert db.query(D.Ledger.submission_id).all() == [(second.id,)]
