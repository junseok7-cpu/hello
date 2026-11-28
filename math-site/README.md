# ∑ 공부 적립 — 수학·과학 서술형 풀이 적립 학습 사이트

아이들이 노트에 풀이를 쓰고 사진을 올리면, 선생님 PC의 **구독 AI(ChatGPT 또는 Claude)** 가 논리 오류를 채점하고, 90점 이상이면 적립금을 쌓아 준다.

```
[학생 폰]──사진 제출──▶ [사이트 (클라우드)] ◀──가져가서 채점──▶ [선생님 PC: 채점 프로그램]
   ▲  이름 로그인            문제 은행·적립·취약단원              codex / claude CLI (구독)
   └──────────── 결과 ◀──────────┘
```

## 과목별 규칙

| | 수학 | 과학 |
|---|---|---|
| 적립 | 하·중 10원, 상 100원 | 모두 20원 (`reward_science`) |
| 하루 최대 | 300원 (`cap_math`) | 200원 (`cap_science`) → 합쳐서 최대 500원 |
| 출제 범위 | 자기 학년 전부 + 아래 학년 '상' | 자기 학년만 |
| 난이도 | 무작위 (취약단원 위주) | 하 → 중 → 상 돌아가며 섞어 냄 |
| 쓰는 것 | 풀이 과정 + 답 | 서술형: 답 + 이유 / 객관식(옳은 것): 정답 + **나머지 선지가 틀린 이유** / 객관식(옳지 않은 것): 정답 + **그 선지가 옳지 않은 이유** / 계산: 풀이 과정 |

객관식 선지는 지우지 않고 그대로 낸다. 문제마다 '문제 유형'(서술형·계산형·객관식 2종)을 정해 두면 학생 화면에 "노트에 쓸 것"이 뜨고 채점 기준도 바뀐다.

## 공통 규칙 (요구사항 → 구현)

| 규칙 | 구현 |
|---|---|
| 90점 이상 적립 | 설정 `pass_score` |
| 하루 최대 300원 | 설정 `daily_cap`. 상 승인 대기 금액도 그날 한도에 미리 잡아 둠. 넘으면 "오늘 한도 도달"로 기록 |
| 3번 미달 → 답지 공개, 한 달 뒤 재제출 | 설정 `max_fails`, `lock_days`. 재도전 통과는 **절반 적립** (5원 / 50원) |
| 상 문제는 선생님 승인 후 적립 | `/t/approvals`. 반려하면 오답 1회로 처리 |
| 취약단원 한눈에 | 선생님 대시보드 단원별 색깔표 |
| 취약단원 기준 | 중 오답률 ≥50% (표본 20문제), 상 오답률 ≥70% (표본 10문제). 설정에서 변경 |
| 표본 전엔 무작위, 이후 취약단원 위주 | 취약단원이 있으면 70%는 취약단원, 30%는 전체에서 무작위 (`weak_ratio`) |
| 학년 범위 | 자기 학년은 전 난이도, 아래 학년은 '상'만 |
| 논리 오류 채점 + 이의신청 | `grader/prompts.py`. 학생에게는 힌트만, 틀린 부분 목록은 선생님만 봄 |
| 접속 | 디스코드에 올린 비밀 링크로 들어와 **이름만** 입력 (선생님이 등록한 이름만 통과). 선생님은 비밀번호 |
| 건너뛰기 | 오늘의 문제 하루 1번 |
| 하루 한도 초과 | 계속 풀 수 있고 적립만 막힘 |
| 월간 보고서 | 매월 28일, 전월 28일~이번 달 27일 학생별 통계 + AI 총평 (`보고서` 메뉴, 인쇄/PDF) |

## 1. 사이트 올리기 (클라우드, 무료)

문제·사진은 모두 DB에 저장하므로 DB 하나만 있으면 된다.

1. https://neon.tech 에서 무료 Postgres 만들기 → 연결 주소 복사 (`postgresql://...`)
2. https://render.com → New → **Blueprint** → 이 저장소 선택 (저장소 맨 위 `render.yaml` 사용)
3. 환경변수 채우기: `DATABASE_URL`, `BASE_URL`(예: `https://math-site.onrender.com`), `TEACHER_PASSWORD`
4. 배포 후 `GRADER_TOKEN`(채점 PC에 넣을 값)과 `ACCESS_KEY` 값을 복사해 둔다
5. 디스코드 채널에 `https://<사이트주소>/join/<ACCESS_KEY>` 링크를 올린다 (이 링크로 들어온 기기만 이름 로그인 가능)
6. 선생님으로 들어가 **학생** 메뉴에서 7명 이름·학년 등록

> Render 무료 요금제는 15분 동안 아무도 안 쓰면 잠들어서 첫 접속이 30초쯤 걸린다. 거슬리면 유료($7/월)로 올리면 된다.

## 2. 채점 PC 준비 (선생님 컴퓨터)

1. Python 3.11+ 와 Node.js 설치
2. 쓰려는 구독 CLI 설치 후 로그인 (둘 다 해 두면 설정에서 바꿔 쓸 수 있다)
   - ChatGPT: `npm i -g @openai/codex` → `codex login` (ChatGPT 계정으로 로그인)
   - Claude: `npm i -g @anthropic-ai/claude-code` → `claude` 실행해 로그인
3. `cd math-site/grader` → `pip install -r requirements.txt`
4. `config.env.example`을 `config.env`로 복사해 `SITE_URL`, `GRADER_TOKEN` 입력
5. `python worker.py` 실행 → 켜 두기. 대시보드에 **채점 PC: 켜짐**이 뜨면 정상

PC가 꺼져 있는 동안 들어온 제출은 쌓여 있다가 켜면 순서대로 채점된다.

## 3. 문제 넣기 (두 가지 방법)

- **Claude에게 맡기기**: 문제집·답지 PDF(또는 사진)를 `math-site/inbox/`에 올리고 "inbox 문제집 등록해 줘"라고 하면 Claude가 문제별로 나눠 단원·난이도를 붙이고 답지와 짝지어 `tools/upload_bundle.py`로 올린다.
- **사이트에서 직접**: 선생님 메뉴 **PDF 등록**에 문제 PDF(+답지 PDF)를 올리면 채점 PC가 처리해 **초안**으로 넣는다.

어느 쪽이든 **문제 은행 → 초안**에서 확인하고 **출제**를 눌러야 학생에게 나간다.

## 로컬에서 시험해 보기

```bash
cd math-site
pip install -r requirements.txt
uvicorn app.main:app --reload     # http://localhost:8000 (선생님 비밀번호 기본값: teacher)
cd grader && python worker.py                  # 다른 창에서
python -m pytest tests                         # 규칙 테스트
```

## 파일

- `app/logic.py` 출제·적립·잠금·취약단원 규칙
- `app/main.py` 화면과 채점 PC용 API
- `app/reports.py` 월간 보고서
- `app/curriculum.py` 기본 단원 목록 (사이트 **단원** 메뉴에서 수정)
- `grader/worker.py` 채점 프로그램, `grader/prompts.py` 채점 기준 문구
- `tools/upload_bundle.py` Claude가 정리한 문제 묶음 업로드
