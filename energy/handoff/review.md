# 검증 결과 — Gemini 2차 인수인계(gemini_v2.md) 대조 (2026-11-28, Claude)

1. Gemini가 "신규 완료"라고 한 LNG 일별 예측·풍력/소수력 이상 후보 알림은 저장소에 없다.
   - results.json 키: A,B,C,D,interval,region,monthly_nRMSE,importance_*,night_share*,kpx_day,metered,komipo_fix,fuelcell,solar_peer,follow,demand_profile_2021,taean,nuclear,supply2025,fig_* → `lng_pred`, `wind_hydro` 없음
   - analyze.py(344줄)에 LNG 예측·풍력/소수력 코드 없음. figures에 f11, f12 없음. index.html 없음. 최종보고서.docx는 기존 버전.
   - 원 데이터(energy/data/)는 gitignore라 이 세션에서는 재계산 불가.
2. 저장소와 다른 수치
   - 2025 최대전력: Gemini 93,615 MW(8/6) ← audit.py가 열 이름 밀림 보정 '전' 값. 보정 후 results.json은 95,951 MW(2025-08-25).
   - 태양광 전체/계량: Gemini 30,583 / 8,925 MW → 저장소 30,609 / 8,934 MW (29.2%는 동일). 30,583·8,925는 저장소 어디에도 없음.
   - 이용률 학습 bias +0.43%p는 실험 D(lag 없는 모델) 값. 주 모델 LightGBM bias는 +0.14%p. Gemini 문서는 nRMSE 14.37%(원시)와 bias +0.43(CF)을 섞어 써서 비교 기준이 불분명.
   - energy_data_lite.xlsx 일별 GBDT(nMAE 2.85 등)는 results.json에 없음.
   - 연료전지 51구간/115일은 results.json(events 합 51, alerts 합 115)과 일치. 원 HANDOFF는 "51건"이라 표현.
3. Gemini 자신의 원칙 1("results.json에 있는 수치만")을 Gemini 문서 스스로 어기고 있음.
4. 남은 작업 정의는 타당: deck.js(17장)·미리캔버스(30p)에 반영, 파트별 대본, 마감 체크리스트.

## GPT 상의 시도
- api.openai.com 키는 등록됐지만 OpenAI 계정 크레딧이 0(`credit_balance_exhausted`)이라 응답을 받지 못했다.
- 대신 `GPT_PROMPT.md`를 만들어 두었다. ChatGPT 창에 그대로 붙여 넣으면 같은 검토를 받을 수 있다. 크레딧을 충전하면 Claude가 API로 직접 상의할 수 있다.

## Claude가 보완한 것
- `analyze_extra.py`: LNG 일별 예측과 풍력·소수력 이상 후보 알림을 재현할 수 있는 코드. 가짜 데이터로 실행 확인. **실제 수치는 원 데이터로 돌려야 나온다.**
- LNG 예측에 "전날 수요만 입력(현실 조건)"을 추가했다. 당일 관측 수요를 넣는 Gemini 방식은 미래 정보를 쓰는 상한선이라 단독으로 발표하면 과대평가로 보일 수 있다.
- 풍력 0건 해석을 바로잡았다. 이용률 중앙값이 약 10%인 설비에 "15%p 하락" 조건은 거의 성립하지 않는다. 0건은 "이상 없음"이 아니라 "규칙 부적합"이다. 0 발전 일수와 최장 연속 0 발전 일수도 같이 기록한다.
- `build/deck.js`: results.json에 `lng_pred`·`wind_hydro`가 있으면 슬라이드 2장(LNG 예측, 풍력·소수력)을 자동 추가한다. pptx 스킬이 없는 환경에서도 빌드된다.
- `report/발표대본.md`: 파트 ①~④ 대본과 예상 질문. 미검증 수치는 【검증 대기】로 비워 두었다.
