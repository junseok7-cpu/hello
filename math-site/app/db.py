"""DB 모델. 로컬은 SQLite, 클라우드는 DATABASE_URL(Postgres)로 바꾸면 된다."""
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, Integer, LargeBinary,
                        String, Text, UniqueConstraint, create_engine)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

KST = timezone(timedelta(hours=9))


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  # DB에는 UTC naive로 저장


def kst_today() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///" + os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data.sqlite3"))
if DATABASE_URL.startswith("postgres://"):  # Heroku/Render 형식 보정
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}
                       if DATABASE_URL.startswith("sqlite") else {}, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()

GRADES = ["중1", "중2", "중3", "고1", "고2", "고3"]
DIFFS = ["하", "중", "상"]


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    discord_id = Column(String(40), unique=True)
    name = Column(String(80), nullable=False)
    role = Column(String(10), default="student")  # student | teacher
    grade = Column(String(4))  # 중1..고3, 선생님이 지정
    active = Column(Boolean, default=True)
    current_problem_id = Column(Integer, ForeignKey("problems.id"))
    created_at = Column(DateTime, default=now)


class Unit(Base):
    __tablename__ = "units"
    id = Column(Integer, primary_key=True)
    grade = Column(String(4), nullable=False)
    order = Column(Integer, default=0)
    name = Column(String(120), nullable=False)
    __table_args__ = (UniqueConstraint("grade", "name"),)


class Blob(Base):
    __tablename__ = "blobs"
    id = Column(Integer, primary_key=True)
    mime = Column(String(60), default="image/jpeg")
    data = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime, default=now)


class Problem(Base):
    __tablename__ = "problems"
    id = Column(Integer, primary_key=True)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False)
    difficulty = Column(String(2), nullable=False)  # 하 중 상
    source = Column(String(200), default="")  # 예: 쎈 중1-1 p.12 #34
    body = Column(Text, default="")  # 문제 (마크다운 + LaTeX $...$)
    image_id = Column(Integer, ForeignKey("blobs.id"))  # 그림/원본 잘라낸 이미지
    answer = Column(Text, default="")  # 최종 답
    solution = Column(Text, default="")  # 풀이 (답지)
    solution_image_id = Column(Integer, ForeignKey("blobs.id"))
    status = Column(String(10), default="draft")  # draft | published
    import_job_id = Column(Integer, ForeignKey("import_jobs.id"))
    created_at = Column(DateTime, default=now)
    unit = relationship("Unit")

    @property
    def grade(self):
        return self.unit.grade if self.unit else None

    @property
    def reward(self):
        return 100 if self.difficulty == "상" else 10


class StudentProblem(Base):
    """학생-문제별 진행 상태."""
    __tablename__ = "student_problems"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    problem_id = Column(Integer, ForeignKey("problems.id"), nullable=False)
    # waiting(채점 대기) | open(다시 도전) | locked(답지 공개, 한 달 잠금) | pending(상 승인 대기) | solved
    state = Column(String(10), default="waiting")
    fail_count = Column(Integer, default=0)  # 이번 라운드 실패 횟수 (3회면 잠금)
    locked_until = Column(DateTime)
    is_retry = Column(Boolean, default=False)  # 잠금 후 재도전 라운드 → 적립 절반
    solution_revealed = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=now, onupdate=now)
    problem = relationship("Problem")
    __table_args__ = (UniqueConstraint("user_id", "problem_id"),)


class Submission(Base):
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    problem_id = Column(Integer, ForeignKey("problems.id"), nullable=False)
    image_ids = Column(String(200), default="")  # "3,4"
    typed_answer = Column(String(300), default="")
    status = Column(String(10), default="queued")  # queued | grading | graded | error
    claimed_at = Column(DateTime)
    score = Column(Integer)
    feedback = Column(Text, default="")
    answer_read = Column(String(300), default="")
    ai_errors = Column(Text, default="")  # AI가 찾은 틀린 부분 (선생님만 봄)
    engine = Column(String(20), default="")
    kst_date = Column(String(10), default=kst_today)  # 적립 한도 계산 기준일 (제출일)
    is_retry = Column(Boolean, default=False)
    # none | credited | pending(상 승인 대기) | rejected | capped(한도 초과)
    reward_status = Column(String(10), default="none")
    reward_amount = Column(Integer, default=0)
    appeal_status = Column(String(10), default="none")  # none | open | accepted | rejected
    appeal_text = Column(Text, default="")
    teacher_note = Column(Text, default="")
    created_at = Column(DateTime, default=now)
    graded_at = Column(DateTime)
    user = relationship("User")
    problem = relationship("Problem")

    @property
    def images(self):
        return [int(x) for x in self.image_ids.split(",") if x]

    @property
    def passed(self):
        return self.score is not None and self.score >= 90


class Ledger(Base):
    __tablename__ = "ledger"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Integer, nullable=False)  # +적립 / -지급
    kind = Column(String(10), default="reward")  # reward | payout | adjust
    submission_id = Column(Integer, ForeignKey("submissions.id"))
    kst_date = Column(String(10), default=kst_today)
    memo = Column(String(200), default="")
    created_at = Column(DateTime, default=now)


class ImportJob(Base):
    __tablename__ = "import_jobs"
    id = Column(Integer, primary_key=True)
    title = Column(String(200), default="")
    grade = Column(String(4))
    problem_blob_id = Column(Integer, ForeignKey("blobs.id"))
    answer_blob_id = Column(Integer, ForeignKey("blobs.id"))
    status = Column(String(10), default="queued")  # queued | working | done | error
    claimed_at = Column(DateTime)
    log = Column(Text, default="")
    created_at = Column(DateTime, default=now)


class Setting(Base):
    __tablename__ = "settings"
    key = Column(String(40), primary_key=True)
    value = Column(String(400), default="")


DEFAULT_SETTINGS = {
    "engine": "codex",          # codex(ChatGPT 구독) | claude(Claude 구독)
    "pass_score": "90",
    "daily_cap": "300",
    "mid_sample": "20",         # 중 문제 표본 수
    "mid_wrong": "0.5",         # 중 오답률 기준
    "hi_sample": "10",          # 상 문제 표본 수
    "hi_wrong": "0.7",          # 상 오답률 기준
    "weak_ratio": "0.7",        # 취약단원이 있을 때 그 단원에서 낼 비율
    "lock_days": "30",
    "max_fails": "3",
    "last_grader_seen": "",
}


def get_setting(db, key):
    s = db.get(Setting, key)
    return s.value if s else DEFAULT_SETTINGS.get(key, "")


def set_setting(db, key, value):
    s = db.get(Setting, key)
    if s:
        s.value = str(value)
    else:
        db.add(Setting(key=key, value=str(value)))


def init_db():
    Base.metadata.create_all(engine)
    from .curriculum import seed_units
    with SessionLocal() as db:
        seed_units(db)
        db.commit()
