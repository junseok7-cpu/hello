# Antigravity 작업 지시문 — 발전원별 AI 예측·관리 시스템

> 사용법: Google Antigravity에서 이 저장소(`junseok7-cpu/hello`)를 연 뒤, 아래 ``` 안의 내용을 에이전트에게 그대로 붙여 넣는다.
> **2026-11-28 갱신**: 원 데이터는 이제 `python fetch_data.py`로 공공데이터포털에서 바로 받을 수 있고, Claude가 이미 재실행해 결과를 커밋했다. 그래서 Antigravity의 일은 **작업 A(Gemini 로컬 파일 회수)와 작업 B의 교차 확인**만 남았다.

```
너는 대학 팀 프로젝트 「발전원별 AI 예측·관리 시스템」의 데이터 실행 담당이다. Claude(클라우드)와 분업한다. Claude에게는 원 데이터가 없고, 너에게는 있다. 너는 "실행하고 결과를 커밋"하는 일만 한다. 대본·보고서 문장·디자인은 Claude가 한다.

## 먼저 읽기
- energy/handoff/HANDOFF_v3.md (기준 문서. 특히 1장 수치 상태표와 3장 원칙)
- energy/HANDOFF.md 2장(데이터 10종)과 8장(다시 실행하기)

## 준비
1. git fetch origin && git checkout ccr-2740b36c-yflj71 && git pull
2. cd energy && python fetch_data.py   (공공데이터포털에서 원 데이터 9종을 data/에 받는다. supply_daily_2025.csv는 포털에 없어 받지 않으며 analyze.py가 이전 값을 유지한다)
3. pip install pandas numpy lightgbm scikit-learn matplotlib pyarrow

## 작업 A — Gemini가 로컬에 만든 파일 확인 (있을 때만)
- 이 PC에 Gemini가 만든 f11_lng_pred.png, f12_wind_hydro.png, index.html, 수정된 analyze.py, 최종보고서.docx가 있는지 찾는다.
- 있으면 energy/handoff/gemini_local/ 폴더에 그대로 복사해 커밋한다. energy/ 안의 원래 파일을 덮어쓰지 않는다.
- 없으면 "Gemini 로컬 산출물 없음"이라고 보고한다.

## 작업 B — 교차 확인(Claude 결과가 다른 PC에서도 같은지)
1. cd energy
2. python analyze.py   (약 1~2분. results/results.json, figures/f1~f10 재생성. 보완 실험 solar_issue_14·solar_interval_issue_14·fuelcell_cusum도 함께 계산됨)
3. python analyze_extra.py   (수 초. results.json에 lng_pred·wind_hydro 추가, figures/f11_lng_pred.png·f12_wind_hydro.png 생성)
4. 확인할 것:
   - git diff energy/results/results.json 으로 Claude가 커밋한 값과 달라진 키가 있는지 본다. 같으면 "차이 없음", 다르면 키와 값을 보고한다. 결과 파일은 고치지 않는다.
   - lng_pred.models, wind_hydro.plants, solar_issue_14, solar_interval_issue_14(calibrated와 by_month), fuelcell_cusum.plants 전체를 그대로 보고한다. results.json에 errors 키가 있으면 그 내용도 보고한다.
   - f11, f12 그림을 열어 글자가 깨지지 않았는지 본다(한글 폰트 없으면 analyze_extra.py 맨 위 폰트 목록에 이 PC의 폰트 경로를 추가).
5. 오류가 나면 코드를 크게 바꾸지 말고, 오류 메시지와 해당 CSV의 열 이름(head 3줄)을 보고한다.

## 작업 C — 커밋과 보고
- 커밋 대상: (있으면) energy/handoff/gemini_local/ 만. results.json·figures는 차이가 있어도 커밋하지 말고 보고만 한다.
- 커밋하지 않는 것: energy/data/ (gitignore, 공공데이터 원본)
- 커밋할 것이 있으면 메시지 "Add Gemini local outputs for review" → git push origin ccr-2740b36c-yflj71
- 마지막에 아래 형식으로 보고한다. 이 보고를 사용자가 Claude에게 전달한다.

  [Antigravity 보고]
  - 커밋 해시:
  - 작업 A: (복사한 파일 목록 또는 "없음")
  - 기존 수치 일치 여부: (일치 / 다른 항목과 값)
  - lng_pred.models: (JSON 그대로)
  - wind_hydro.plants: (JSON 그대로)
  - solar_issue_14 / solar_interval_issue_14 / fuelcell_cusum: (JSON 그대로)
  - errors: (있으면)
  - 문제·질문:

## 규칙
- 수치를 직접 만들거나 반올림해 바꾸지 않는다. 스크립트가 낸 값만 쓴다.
- 이상탐지 결과는 "이상 후보 알림"이라고 부른다.
- energy/report/, energy/build/, energy/handoff/HANDOFF_v3.md 는 수정하지 않는다(Claude 담당). 충돌을 막기 위해서다.
- 시간이 남으면(선택) index.html 대시보드가 Gemini 로컬 산출물에 있을 경우, 하드코딩된 숫자를 results.json 값과 대조한 표를 energy/handoff/index_check.md로 남긴다. 고치지는 않는다.
```

## Claude가 받은 뒤 할 일
보고를 받으면 Claude가 `git pull` → 결과 검토 → 대본의 【검증 대기】 채우기 → report.js·deck.js 재생성 → 미리캔버스 반영 순으로 진행한다.
