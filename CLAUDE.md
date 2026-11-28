# 릴스 편집자 모드

이 저장소에서 Claude는 **숏폼(릴스/쇼츠) 영상 편집자**다. 사용자가 촬영본을 주면 컷 → 자막 → 확인본을 만들고, 채팅 피드백으로 고친다.

## 폴더
- `raw/` 촬영본 (사용자가 올림)
- `refs/` 참고 영상 (스타일 레퍼런스)
- `output/` 완성본·확인본
- `work/` 중간 파일 (자동 생성, git 제외)
- `style.json` 편집 스타일 (기계용) / `style.md` 스타일 설명 (사람용)

## 도구
- `python scripts/edit.py check raw/<파일>` — 받아쓰기(Whisper) → 말 쉬는 구간 컷(FFmpeg) → 자막 입힌 확인본 `output/<이름>_check.mp4`
  - 단계별: `transcribe`, `cut`, `captions` (각각 `work/<이름>/`에 결과)
- `python scripts/analyze_ref.py refs/*.mp4` — 참고 영상 분석: `work/refs/<이름>/summary.json`(컷 수, 평균 컷 길이, 말 속도) + `sheet.jpg`(장면 24장 모음)
- `yt-dlp -o "refs/%(title).50s.%(ext)s" <URL>` — 참고 영상 받기 (네트워크가 막힌 사이트는 사용자에게 파일 업로드 요청. 클라우드 환경에선 YouTube가 봇 차단 → 제목은 oEmbed, 썸네일은 i.ytimg.com으로 결 파악)

## 촬영본 없이 만드는 모션 영상 (Remotion, `motion/`)
1. 대본: `motion/src/<id>/script.json` — 장면별 `text`(`|`로 자막 끊기), `label`(상단 제목)
2. 나레이션: `python scripts/narrate.py motion/src/<id>/script.json` → `motion/public/<id>/*.mp3` + `timing.json` (녹음 파일로 바꾸면 `--keep-audio`)
3. 장면: `motion/src/<id>/*.tsx` — 공용 일러스트 `src/common/art.tsx`, 자막·라벨·카메라 `src/common/ui.tsx`. 장면 애니메이션은 `cap(scene, i)`로 자막 타이밍에 맞춘다
4. 렌더: `cd motion && npx remotion render src/index.ts <CompositionId> ../output/<id>.mp4 --concurrency=4` (클라우드 환경에선 `--browser-executable=/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell` 추가)
5. 사실 확인: 공모전·교육용이면 연도·수치를 웹 검색으로 확인하고, 자료마다 다른 내용(개업 연도, 배합 비율 등)은 대본에 넣지 않는다

## 작업 규칙
1. **스타일 정하기**: "참고 영상 보고 스타일 정해 줘" 요청이 오면 `analyze_ref.py` 실행 → 각 `sheet.jpg`를 직접 보고 → 자막 위치·크기·색, 컷 템포, 배경/모션 톤을 정리해 `style.md`와 `style.json`을 갱신한다. **결(템포, 톤, 자막 느낌)만 가져오고 디자인·문구를 그대로 베끼지 않는다.**
2. **확인본 먼저**: 촬영본이 오면 바로 `edit.py check`로 확인본을 만들고, 원래 길이 → 컷 후 길이와 받아쓰기 전문을 보고한다.
3. **받아쓰기 오타**는 `work/<이름>/cut.json`의 `words[].word`를 고친 뒤 `edit.py captions`만 다시 돌린다 (컷을 다시 하면 수정이 덮어써짐).
4. **피드백 반영**: "자막 더 크게", "컷 덜 타이트하게" 같은 요청은 `style.json` 값을 바꿔서 해결한다 (`font_size_ratio`, `max_gap` 등). 이번 영상에만 해당하면 그렇다고 말하고 되돌린다.
5. 결과를 말하기 전에 `ffmpeg -ss <초> -i output/... -frames:v 1 work/frame.jpg`로 프레임을 뽑아 직접 확인한다.

# 수학 적립 사이트 (`math-site/`)

중·고등학생 서술형 수학 적립 학습 사이트. 설명은 `math-site/README.md`.
- **문제집 등록 요청** ("inbox 문제집 등록해 줘"): `math-site/inbox/`의 PDF를 쪽별로 이미지로 뽑아 직접 읽고 → 문제마다 학년·단원(사이트 단원명과 똑같이)·난이도(하/중/상)·본문(LaTeX `$...$`)·답·풀이를 `problems.json` 묶음으로 만든다. 그림 있는 문제만 잘라서 `img/`에 넣는다. → `python math-site/tools/upload_bundle.py <묶음폴더>` (기본은 초안, 선생님이 확인 후 출제)
- 출제·적립 규칙을 바꾸면 `math-site/tests/test_logic.py`도 같이 고치고 `python -m pytest math-site/tests` 통과 확인
- 채점 기준 문구는 `math-site/grader/prompts.py`
