기상청 관측 날씨를 넣은 실험을 추가하고, 발표자료 파트 4와 보고서 7.8절에 반영했습니다. `python3 analyze_plan.py`는 정상 종료했고, `plan.with_weather`를 제외한 기존 JSON 값은 모두 동일했습니다. 두 JavaScript 파일은 구문 검사만 했습니다.

| 2025년 9~12월, 2,928시간 | AI(날씨 없음) | AI(관측 날씨) |
|---|---:|---:|
| 대기 발전량(P95) | 8,119 MW | 7,284 MW |
| 실제보다 많이 준비한 전력량 | 4,079.2 GWh | 4,015.0 GWh |
| 수요 예측 오차(MAPE) | 4.08% | 3.82% |
| 태양광 오차(설비용량 대비) | 4.07% | 2.53% |
| 풍력 오차(설비용량 대비) | 13.34% | 10.11% |

관측 날씨를 넣었을 때 대기 발전량은 날씨 없는 AI보다 **835 MW** 줄었습니다. 지난주 같은 시각 기준으로는 **5,818 MW** 줄었고, 실제보다 많이 준비한 전력량은 **2,535.3 GWh** 줄었습니다. 대상 시각의 실제 관측을 사용했으므로 실제 예보보다 좋은 참고값입니다.

1~8월 자료에서 관측 시각을 1시간 앞당겼을 때 태양광 발전량과 일사의 상관이 0.9460에서 0.9636으로 높아져 이 정렬을 적용했습니다.

변경 파일은 [analyze_plan.py](/home/user/hello/energy/analyze_plan.py), [results.json](/home/user/hello/energy/results/results.json), [f29_plan_weather.png](/home/user/hello/energy/figures/f29_plan_weather.png), [deck_final.js](/home/user/hello/energy/build/deck_final.js), [report.js](/home/user/hello/energy/build/report.js)입니다.