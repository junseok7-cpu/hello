2025년 11월 17~30일 07~18시, 총 168시간을 비교했습니다. 실제 기상청 예보를 같은 관측 학습 모델에 넣었을 때 **풍력 오차는 3.02%p 커졌고, 순수요 대기 발전량은 638 MW 늘었습니다.** 태양광과 전력수요 오차는 소폭 줄었습니다.

| 지표 | 날씨 없음 | 관측 날씨 | 실제 예보 |
|---|---:|---:|---:|
| 태양광 오차 · 설비용량 대비 | 5.50% | 5.76% | 5.74% |
| 풍력 오차 · 설비용량 대비 | 18.16% | 16.93% | 19.95% |
| 전력수요 MAPE | 4.88% | 4.44% | 4.25% |
| 순수요 대기 발전량 P95 | 8,551 MW | 7,988 MW | 8,626 MW |

예보 파일 7개는 결측으로 처리했습니다. 서울·부산·제주의 같은 시각 기온을 대조해 `ny`가 바깥, `nx`가 안쪽인 격자 순서를 확인했습니다. 관측은 기존의 1시간 이동을 적용했고 예보는 파일의 대상 시각에 맞췄습니다. 결과는 **11월 낮 시간 2주 표본의 참고값**입니다.

변경 파일은 [analyze_fcst.py](/home/user/hello/energy/analyze_fcst.py), [analyze_plan.py](/home/user/hello/energy/analyze_plan.py), [results.json](/home/user/hello/energy/results/results.json), [f30 그림](/home/user/hello/energy/figures/f30_plan_forecast.png), [발표 슬라이드](/home/user/hello/energy/build/deck_final.js), [보고서](/home/user/hello/energy/build/report.js)입니다. `python3 analyze_fcst.py` 실행과 기존 결과 키 보존을 확인했습니다. Node 빌드는 생략했습니다.