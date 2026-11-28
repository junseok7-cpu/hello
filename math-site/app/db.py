"""DB 모델. 로컬은 SQLite, 클라우드는 DATABASE_URL(Postgres)로 바꾸면 된다."""
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, Index, Integer, LargeBinary,
                        String, Text, UniqueConstraint, create_engine, inspect, text)
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
SUBJECTS = {"math": "수학", "science": "과학"}
# 문제 유형: 학생에게 무엇을 써야 하는지 알려 주고, 채점 기준을 고른다
QTYPES = {
    "essay": "서술형",
    "calc": "계산형",
    "mc_right": "객관식 (옳은 것 고르기)",
    "mc_wrong": "객관식 (옳지 않은 것 고르기)",
}


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    discord_id = Column(String(40), unique=True)
    name = Column(String(80), nullable=False)
    role = Column(String(10), default="student")  # student | teacher
    grade = Column(String(4))  # 중1..고3, 선생님이 지정
    active = Column(Boolean, default=True)
    current_problem_id = Column(Integer, ForeignKey("problems.id"))
    skip_date = Column(String(10), default="")  # 마지막으로 건너뛰기 쓴 날 (KST, 수학)
    current_sci_id = Column(Integer, ForeignKey("problems.id"))  # 과학 오늘의 문제
    skip_date_sci = Column(String(10), default="")
    created_at = Column(DateTime, default=now)


class Unit(Base):
    __tablename__ = "units"
    id = Column(Integer, primary_key=True)
    subject = Column(String(10), default="math", nullable=False)  # math | science
    grade = Column(String(4), nullable=False)
    order = Column(Integer, default=0)
    name = Column(String(120), nullable=False)
    __table_args__ = (UniqueConstraint("subject", "grade", "name"),)


class Blob(Base):
    __tablename__ = "blobs"
    id = Column(Integer, primary_key=True)
    mime = Column(String(60), default="image/jpeg")
    data = Column(LargeBinary)
    storage_key = Column(String(200))
    size = Column(Integer)
    created_at = Column(DateTime, default=now)


class Problem(Base):
    __tablename__ = "problems"
    id = Column(Integer, primary_key=True)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False)
    difficulty = Column(String(2), nullable=False)  # 하 중 상
    qtype = Column(String(10), default="essay")  # QTYPES 참고
    source = Column(String(200), default="")  # 예: 쎈 중1-1 p.12 #34
    body = Column(Text, default="")  # 문제 (마크다운 + LaTeX $...$)
    image_id = Column(Integer, ForeignKey("blobs.id"))  # 그림/원본 잘라낸 이미지
    image_kind = Column(String(8), default="figure")  # full(문제 전체를 잘라낸 것: 글 대신 보여 줌) | figure(그림만)
    answer = Column(Text, default="")  # 최종 답
    solution = Column(Text, default="")  # 풀이 (답지)
    solution_image_id = Column(Integer, ForeignKey("blobs.id"))
    status = Column(String(10), default="draft")  # draft | published
    review_note = Column(Text, default="")  # 자동 등록 때 확인이 필요한 점 (답지 없음, 흐린 글자 등)
    import_job_id = Column(Integer, ForeignKey("import_jobs.id"))
    created_at = Column(DateTime, default=now)
    unit = relationship("Unit")

    @property
    def grade(self):
        return self.unit.grade if self.unit else None

    @property
    def subject(self):
        return self.unit.subject if self.unit else "math"


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
    retry_count = Column(Integer, nullable=False, server_default="0")
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
    __table_args__ = (Index("uq_ledger_submission", "submission_id", unique=True),)
    kst_date = Column(String(10), default=kst_today)
    memo = Column(String(200), default="")
    created_at = Column(DateTime, default=now)


class ImportJob(Base):
    __tablename__ = "import_jobs"
    id = Column(Integer, primary_key=True)
    title = Column(String(200), default="")
    subject = Column(String(10), default="math")
    grade = Column(String(4))
    blob_ids = Column(String(400), default="")     # 올린 원본 파일들 (문제·답지 섞여도 됨), "3,4"
    filenames = Column(Text, default="")            # 같은 순서의 파일 이름, 줄바꿈 구분
    report = Column(Text, default="")              # 등록 보고서 (빠진 번호, 짝 없는 답지 등)
    status = Column(String(10), default="queued")  # queued | working | done | error
    claimed_at = Column(DateTime)
    log = Column(Text, default="")
    created_at = Column(DateTime, default=now)


class Report(Base):
    """월간 보고서 (매월 28일, 전월 28일 ~ 이번 달 27일)."""
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    period_start = Column(String(10), nullable=False)
    period_end = Column(String(10), nullable=False)
    data = Column(Text, default="{}")  # 통계 JSON
    ai_comment = Column(Text, default="")
    status = Column(String(10), default="queued")  # queued(AI 총평 대기) | working | done
    claimed_at = Column(DateTime)
    created_at = Column(DateTime, default=now)
    user = relationship("User")
    __table_args__ = (UniqueConstraint("user_id", "period_end"),)


class Setting(Base):
    __tablename__ = "settings"
    key = Column(String(40), primary_key=True)
    value = Column(String(400), default="")


DEFAULT_SETTINGS = {
    "engine": "codex",          # codex(ChatGPT 구독) | claude(Claude 구독)
    "pass_score": "90",
    "cap_math": "300",          # 수학 하루 최대 적립
    "cap_science": "200",       # 과학 하루 최대 적립
    "reward_science": "20",     # 과학 문제 하나당 적립
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


def migrate_blob_schema(conn):
    columns = {c["name"]: c for c in inspect(conn).get_columns("blobs")}
    if not columns["data"]["nullable"] and conn.dialect.name == "sqlite":
        with conn.begin_nested():
            conn.execute(text("CREATE TABLE blobs_new (id INTEGER PRIMARY KEY, mime VARCHAR(60), "
                              "data BLOB, created_at DATETIME, storage_key VARCHAR(200), size INTEGER)"))
            names = ", ".join(c.name for c in Blob.__table__.columns if c.name in columns)
            conn.execute(text(f"INSERT INTO blobs_new ({names}) SELECT {names} FROM blobs"))
            conn.execute(text("DROP TABLE blobs"))
            conn.execute(text("ALTER TABLE blobs_new RENAME TO blobs"))
        return
    if not columns["data"]["nullable"]:
        conn.execute(text("ALTER TABLE blobs ALTER COLUMN data DROP NOT NULL"))
    for name, sql_type in (("storage_key", "VARCHAR(200)"), ("size", "INTEGER")):
        if name not in columns:
            guard = "IF NOT EXISTS " if conn.dialect.name == "postgresql" else ""
            conn.execute(text(f"ALTER TABLE blobs ADD COLUMN {guard}{name} {sql_type}"))


def init_db():
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        migrate_blob_schema(conn)
        if "retry_count" not in {c["name"] for c in inspect(conn).get_columns("submissions")}:
            conn.execute(text("ALTER TABLE submissions ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0"))
        if "uq_ledger_submission" not in {i["name"] for i in inspect(conn).get_indexes("ledger")}:
            duplicate = conn.execute(text(
                "SELECT 1 FROM ledger WHERE submission_id IS NOT NULL "
                "GROUP BY submission_id HAVING COUNT(*) > 1 LIMIT 1"
            )).first()
            if not duplicate:
                conn.execute(text("CREATE UNIQUE INDEX uq_ledger_submission ON ledger (submission_id)"))
    from .curriculum import seed_units
    with SessionLocal() as db:
        seed_units(db)
        db.commit()
