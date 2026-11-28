"""구독 CLI로 AI 호출: ChatGPT(Codex CLI) 또는 Claude(Claude Code). API 키를 쓰지 않는다.

프롬프트는 stdin으로 넘긴다 (Windows에서 .cmd 실행 시 줄바꿈·특수문자가 깨지지 않게).
"""
import json
import os
import re
import shutil
import subprocess
import tempfile

TIMEOUT = int(os.environ.get("ENGINE_TIMEOUT", "300"))


class EngineError(Exception):
    pass


def _exe(name):
    path = shutil.which(name)
    if not path:
        raise EngineError(f"'{name}' 명령을 찾을 수 없어요. 설치하고 로그인했는지 확인하세요.")
    return path


def run_codex(prompt: str, images: list[str], workdir: str) -> str:
    out = os.path.join(workdir, "codex_last.txt")
    cmd = [_exe("codex"), "exec", "-", "--skip-git-repo-check", "--sandbox", "read-only",
           "--color", "never", "--ephemeral", "-o", out]
    if os.environ.get("CODEX_MODEL"):
        cmd += ["-m", os.environ["CODEX_MODEL"]]
    for img in images:
        cmd += ["-i", img]
    r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                       cwd=workdir, timeout=TIMEOUT)
    if r.returncode != 0:
        raise EngineError("codex 실패: " + (r.stderr or r.stdout)[-800:])
    if os.path.exists(out):
        with open(out, encoding="utf-8") as f:
            return f.read()
    return r.stdout


def run_claude(prompt: str, images: list[str], workdir: str) -> str:
    names = ", ".join(os.path.basename(p) for p in images)
    prompt = (f"먼저 Read 도구로 이 폴더의 이미지 파일을 모두 열어 보고 답하라: {names}\n\n" + prompt)
    cmd = [_exe("claude"), "-p", "--output-format", "json", "--allowedTools", "Read"]
    if os.environ.get("CLAUDE_MODEL"):
        cmd += ["--model", os.environ["CLAUDE_MODEL"]]
    r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                       cwd=workdir, timeout=TIMEOUT)
    if r.returncode != 0:
        raise EngineError("claude 실패: " + (r.stderr or r.stdout)[-800:])
    try:
        return json.loads(r.stdout).get("result", "")
    except json.JSONDecodeError:
        return r.stdout


def ask(engine: str, prompt: str, images: list[str], workdir: str) -> dict:
    """이미지를 workdir에 둔 상태로 AI에게 묻고 JSON을 돌려받는다."""
    fn = {"codex": run_codex, "claude": run_claude}.get(engine)
    if fn is None:
        raise EngineError("알 수 없는 엔진: " + engine)
    text = fn(prompt, images, workdir)
    return parse_json(text)


def parse_json(text: str) -> dict:
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    cand = m.group(1) if m else None
    if cand is None:
        s, e = text.find("{"), text.rfind("}")
        if s < 0 or e < 0:
            raise EngineError("AI 응답에 JSON이 없어요: " + text[:300])
        cand = text[s:e + 1]
    try:
        return json.loads(cand)
    except json.JSONDecodeError as ex:
        raise EngineError(f"JSON 해석 실패 ({ex}): " + cand[:300])


def new_workdir():
    return tempfile.mkdtemp(prefix="mathgrader_")
