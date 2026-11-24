# Claude 릴스 편집 시스템

Claude Code를 숏폼 영상 편집자로 쓰는 세팅입니다. 촬영본을 넣으면 **말 쉬는 구간 컷 → 자동 자막 → 확인본**까지 만들고, 채팅으로 수정합니다.

## 세팅 4단계

| 단계 | 내용 | 이 저장소에서 |
|---|---|---|
| 1. 앱 + Code | Claude 데스크톱 앱(또는 claude.ai/code)의 Code에서 이 폴더 열기 | `CLAUDE.md`가 Claude를 "편집자 모드"로 만듦 |
| 2. 폴더 | 촬영본 / 참고 영상 / 완성본 | `raw/` · `refs/` · `output/` |
| 3. 도구 | FFmpeg(자르기·내보내기), Whisper(자막), yt-dlp(참고 영상 받기), Remotion(모션, 다음 단계) | `scripts/edit.py`, `scripts/analyze_ref.py` |
| 4. 스타일 | 참고 영상 3개로 내 스타일 정하기 | `style.md` / `style.json` |

## 설치 (내 컴퓨터에서 쓸 때)

```bash
pip install -r requirements.txt
```

FFmpeg도 필요합니다 (macOS: `brew install ffmpeg`).

## 사용법: Claude에게 이렇게 말하세요

1. **스타일 정하기** (처음 한 번): `refs/`에 참고 영상 3개를 넣고
   > 이 영상 3개 보고 내 편집 스타일 정해 줘. 결만 가져오고, 그대로 베끼진 마.
2. **확인본 만들기**: `raw/`에 촬영본을 넣고
   > raw/오늘영상.mp4 말 쉬는 데는 빼고 확인본 뽑아 줘
3. **수정**: 확인본을 보고 말로 고치기
   > 자막 조금 더 크게, 말하는 단어는 노란색으로 강조해 줘

결과물은 `output/<이름>_check.mp4`에 나옵니다.

## 직접 실행

```bash
python scripts/edit.py check raw/clip.mp4        # 받아쓰기 → 컷 → 자막
python scripts/analyze_ref.py refs/*.mp4         # 참고 영상 분석
```

## 주요 스타일 값 (`style.json`)

- `cut.max_gap`: 이 시간(초)보다 긴 침묵은 자름. 작을수록 타이트
- `captions.font_size_ratio`: 자막 크기 (영상 높이 대비)
- `captions.position`: `lower` / `center` / `upper`
- `captions.max_chars`: 자막 한 덩어리 글자 수
- `captions.highlight_color`: `"#FFE14D"`처럼 넣으면 말하는 단어 강조
- `whisper.model`: `small` (빠름) → `medium` / `large-v3` (정확)

폰트: [Pretendard](https://github.com/orioncactus/pretendard) (SIL OFL 1.1)
