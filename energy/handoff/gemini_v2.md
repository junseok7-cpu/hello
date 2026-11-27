# 인수인계 프롬프트 (Gemini 작성, 2차 업데이트) — 원문 보관용

> 2026-11-28 사용자가 Gemini에게 받아 전달한 문서의 핵심 내용. 검증 결과는 `review.md`, 보완본은 `HANDOFF_v3.md` 참고.

## Gemini가 주장한 신규 완료 항목
- 화력 LNG 일별 예측(2018~20 학습, 2021 시험 365일, 2021 일평균 LNG 447.7 GWh)
  - 피처: 당일 수요(일 합계·최대), 요일, 월 sin/cos, lag1, lag7
  - Persistence: MAE 61.79 / RMSE 81.94 GWh (nMAE 13.80%, nRMSE 18.30%, Skill 0)
  - 선형회귀: MAE 34.19 / RMSE 42.88 GWh (nMAE 7.64%, nRMSE 9.58%, Skill 0.477)
  - GBDT: MAE 35.95 / RMSE 44.40 GWh (nMAE 8.03%, nRMSE 9.92%, Skill 0.458)
- 풍력 2기: 제주상명풍력(1,034일, 중앙 이용률 10.3%) 0건, 양양풍력#1(1일) 0건
- 소수력 4기: 보령화력소수력#1 3구간(3일), #2 14구간(60일), 신보령소수력 9구간(14일), 신서천화력소수력 1구간(8일)
- 산출물: analyze.py에 `lng_pred`·`wind_hydro` 통합, results.json 갱신, f11_lng_pred.png, f12_wind_hydro.png, 최종보고서.docx 1~7장, index.html 대시보드
- 참고 수치: energy_data_lite.xlsx 일별 GBDT nMAE 2.85%, nRMSE 3.71%, Skill 0.436

## Gemini 문서에 적힌 기존 수치 (저장소와 다른 것만)
- 태양광 전체 30,583 MW / 계량 8,925 MW (29.2%)
- 2025 최대전력 93,615 MW (8/6)
- 인천연료전지 설비용량 31,680 kW 정정, KPX 비교 "17개 시도 주간"

## Gemini가 남긴 남은 작업
1. 발표자료(pptx, deck.js, 미리캔버스 30p)에 LNG 예측·풍력/소수력 알림을 파트 ②③④에 반영
2. 파트별 발표 대본 ①~④ (④는 코드 구현 설명, index.html 시연 멘트 포함)
3. 11/30 마감 체크리스트(팀원 이름, 데이터 제공기관 표기, 목차 파트 ④ "코드 구현")

나머지(원칙 5개, 태양광·연료전지·태양광 인접비교·원자력 수치)는 기존 `energy/HANDOFF.md`와 같다.
