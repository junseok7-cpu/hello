"""ChatGPT 구독(Codex CLI)으로 사이트 코드를 검토받는다. 선생님 PC에서 실행.

    python math-site/tools/gpt_review.py            # 검토 → math-site/gpt_review_result.md
    python math-site/tools/gpt_review.py --dry-run  # 보낼 지시문만 보기

GPT는 읽기 전용으로 코드를 읽기만 하고 고치지 않는다. 결과 파일 내용을 Claude에게 붙여 주면
Claude가 하나씩 확인해서 고친다.
"""
import argparse
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # math-site/
FILES = ["app/logic.py", "app/main.py", "app/reports.py", "app/db.py", "app/curriculum.py",
         "app/static/app.js", "app/templates/_macros.html", "app/templates/s_home.html",
         "app/templates/s_problem.html", "app/templates/t_review.html", "app/templates/t_report.html",
         "grader/worker.py", "grader/engines.py", "grader/prompts.py", "tools/upload_bundle.py"]

PROMPT = """너는 독립적이고 깐깐한 코드 리뷰어다. 이 코드는 다른 AI(Claude)가 작성했다. 작성자의 의도를 믿지 말고 실제 문제를 찾아라.
코드를 고치지 말고 읽기만 해라.

[프로젝트] 중1~고1 학생 7명이 쓰는 수학 서술형 적립 학습 사이트 (FastAPI + SQLAlchemy).
학생이 노트 풀이 사진을 올리면, 선생님 PC의 채점 프로그램(grader/worker.py)이 AI로 채점해 결과를 사이트에 돌려준다.

[지켜야 할 규칙]
- 하·중 문제 10원, 상 문제 100원. 90점 이상이면 적립
- 하루 최대 적립 300원 (한국 시간 기준). 넘어도 계속 풀 수 있고 적립만 막는다
- 같은 문제를 3번 미달하면 답지 공개 + 30일 잠금. 30일 뒤 재도전해 통과하면 절반 적립
- 상 문제는 선생님 승인 후 적립. 반려하면 오답 1회
- 오늘의 문제 건너뛰기는 하루 1번
- 학생 학년의 문제는 전 난이도, 아래 학년 문제는 '상'만 출제
- 취약단원: '중' 20문제 이상 중 오답률 50% 이상, 또는 '상' 10문제 이상 중 오답률 70% 이상. 그 전엔 무작위 출제, 이후 취약단원 위주
- 이의신청: 학생이 신청 → 선생님이 점수를 바꿔 인정하거나 기각
- 매월 28일 학생별 월간 보고서 (전월 28일 ~ 이번 달 27일)
- 로그인: 학생은 비밀 링크(/join/<키>)로 들어와 이름만 입력 (의도된 설계이니 지적하지 말 것), 선생님은 비밀번호, 채점 PC는 토큰

[검토할 파일] (math-site/ 폴더 기준, 직접 열어서 읽어라)
{files}

[중점]
1. 적립금 계산 오류, 하루 한도 우회, 같은 제출에 두 번 적립되는 경우 (동시 요청·재시도·이의신청·승인 순서 포함)
2. 학생이 다른 학생 데이터나 아직 받지 않은 문제·답지를 보거나 제출할 수 있는 권한 우회
3. 위 규칙과 다르게 동작하는 부분
4. 서버 오류(500)가 나는 입력, 채점 PC가 꺼지거나 실패했을 때 멈추는 작업
5. 채점 프롬프트 조작(학생이 사진에 지시문을 써서 점수 올리기) 등 보안 문제

[출력] 한국어 마크다운으로:
## 판정: PASS 또는 FAIL (CRITICAL/HIGH가 하나라도 있으면 FAIL)
그다음 문제마다:
### [심각도] 제목
- 위치: 파일:줄
- 문제: 무엇이 어떤 상황에서 잘못되는지 (구체적인 재현 순서)
- 고치는 법: 한두 줄
심각도: CRITICAL=보안·돈·데이터 손실, HIGH=버그·규칙 위반, MEDIUM=유지보수, LOW=사소함.
확실하지 않은 것은 '추측'이라고 표시하고, 문제가 없으면 없다고 써라. 칭찬이나 요약은 쓰지 마라.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--model", default="", help="비우면 Codex 기본 모델")
    a = ap.parse_args()
    files = [f for f in FILES if os.path.exists(os.path.join(ROOT, f))]
    prompt = PROMPT.format(files="\n".join("- " + f for f in files))
    if a.dry_run:
        print(prompt)
        return
    codex = shutil.which("codex")
    if not codex:
        sys.exit("codex 가 없어요. 'npm i -g @openai/codex' 후 'codex login' 하세요.")
    out = os.path.join(ROOT, "gpt_review_result.md")
    cmd = [codex, "exec", "-", "--skip-git-repo-check", "--sandbox", "read-only", "-o", out]
    if a.model:
        cmd += ["-m", a.model]
    print("ChatGPT가 코드를 검토하는 중이에요 (몇 분 걸려요)...")
    r = subprocess.run(cmd, input=prompt, text=True, encoding="utf-8", cwd=ROOT)
    if r.returncode != 0 or not os.path.exists(out):
        sys.exit("검토 실패. 'codex login' 이 되어 있는지 확인하세요.")
    print(f"\n완료! 결과 파일: {out}\n이 파일 내용을 Claude 채팅창에 붙여 넣어 주세요.")


if __name__ == "__main__":
    main()
