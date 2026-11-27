"""50종 공공데이터 목록 생성: report/데이터목록.md, report/catalog.json
실행: python build/catalog.py (analyze*.py 를 모두 돌린 뒤)"""
import json
R = json.load(open('results/results.json', encoding='utf-8'))
P1, P2, P3 = R['public'], R['public2'], R['public3']
f1 = lambda x: f'{x:.1f}'
A, L, W, KP = R['A'], R['lng_pred']['models'], R['wind_hydro']['plants'], R['kpx_day']
g, h, b, n, rs, cu, v, cx = (P1[k] for k in ('geothermal', 'heat_sources', 'biomass', 'nuclear_outage', 'renewables_2025', 'curtailment', 'forecast_value', 'context'))
ws, jw, ks, ew, kf, hm, jf, mi = (P2[k] for k in ('wind_scada', 'jeju_wind', 'khnp_solar', 'ewp_units', 'kospo_fuelcell', 'heat_more', 'jeju_fuel', 'misc'))
q = P3
rb = rs['by_source']
C = []
def add(pk, name, org, part, grp, period, use, result, fig=''):
    C.append(dict(pk=str(pk), name=name, org=org, part=part, group=grp, period=period, use=use, result=result, fig=fig,
                  url=f'https://www.data.go.kr/data/{pk}/fileData.do'))
# ── 기본 9종 ──
add(15151005, '전국 태양광 발전량 예측값 학습데이터', '한국동서발전', '③', '기본', '2020~2024 시간별 · 17개 시도',
    '태양광 하루 전 예측 모델 학습·시험', f"LightGBM nRMSE {A['LightGBM']['nRMSE']}% (어제 값 {A['Persistence']['nRMSE']}%), 오차 {A['LightGBM']['Skill']*100:.0f}% 감소", 'f1·f2·f3')
add(15151010, '전국 태양광 발전량 예측값', '한국동서발전', '③', '기본', '2024-12-02 하루',
    '전력거래소 공식 하루 전 예측과 비교', f"공식 {KP['공식 하루 전 예측']['nRMSE']}% · 우리 모델 {KP['우리 모델(관측 기상 입력)']['nRMSE']}% (관측 기상 입력)", 'f7')
add(15004239, '신재생에너지 발전량', '한국중부발전', '②③', '기본', '2023.11~2026.8 일별 · 설비별',
    '연료전지·풍력·소수력 이상 후보 알림, 태양광 인접 비교', f"연료전지 5기 51구간 115일, 태양광 26곳 272구간", 'f8·f12')
add(15069345, '일별 화력발전량', '한국전력거래소', '②', '기본', '2018~2022 일별 · 지역·연료원별',
    'LNG 수요 추종 분석·일별 예측', f"수요 상관 LNG {R['follow']['corr']['LNG']}, 일별 예측 오차 {L['선형회귀 · 전날 수요만 입력(현실 조건)']['nRMSE']}% (어제 값 {L['어제 값(Persistence)']['nRMSE']}%)", 'f9·f11')
add(15065387, '시간별 발전량(전력수요)', '한국전력거래소', '②', '기본', '2017~2021 시간별',
    '하루 전력수요(LNG 예측 입력)', f"일평균 {R['follow']['mean_GWh']['demand_GWh']} GWh, 변동계수 {R['follow']['cv']['demand_GWh']}", 'f9')
add(15123066, '발전소별 발전량(태안)', '한국서부발전', '②', '기본', '2022.12~2023.12 일별 · 호기별',
    '석탄 화력 이용률·출력 범위', f"태안 10기 평균 이용률 {R['taean']['cf_mean']*100:.1f}%")
add(15002302, '원자력발전소 호기별 발전량 및 이용률', '한국수력원자력', '②', '기본', '2014~2025 연별',
    '원전 이용률 추이·저이용 사례', f"292건 중 50% 미만 28건, 한빛5호기 2021년 {R['nuclear']['hanbit5']['2021']}%", 'f10')
add(15046077, '국내원전 호기별 발전량', '원자력안전위원회', '②', '기본', '2019~2025 연별', '원전 발전량 보조 확인', '이용률 자료와 대조용')
add(15046076, '국내 원자력발전소 현황', '원자력안전위원회', '②', '기본', '2025 기준', '설계수명 만료 시점', f"운영 26기 중 10기 2030년까지 만료")
# ── 1차 16종 ──
add(15126707, '국립세종수목원 지열 이용량', '한국수목원정원관리원', '①', '1차', f"{g['period']} 시간별 · 4개 건물",
    '지열 히트펌프 효율(COP) 이상 후보 알림', f"COP 중앙값 {g['cop_median']}, 효율 30% 이상 하락 {sum(g['cop_drop_alert_days'].values())}일 / {sum(g['judged_days'].values()):,}일", 'f13')
add(15157241, '신재생에너지 생산량', '기후에너지환경부', '①', '1차', '2015~2024 연별', '지열·수열·바이오 성장 추이',
    f"2015→2024 지열 {h['growth_2015_2024']['지열']}배, 수열 {h['growth_2015_2024']['수열']}배", 'f14')
add(15149953, '연도별 공급자별 외부 수열량', '한국지역난방공사', '①', '1차', '연별', '수열 공급원 구성', f"{h['external_heat_year']}년 최대 공급원: {list(h['external_heat_latest'])[0]}")
add(15123991, '시간대별 수열량 정보', '한국지역난방공사', '①', '1차', h['sejong_period'] + ' 시간별', '세종 수열 시간대 패턴', '시간대별 평균 수열량 산출')
add(15150813, '바이오매스 연료분석결과', '한국동서발전', '②', '1차', b['period'] + ' · 109건', '바이오 연료 품질 편차',
    f"수분–발열량 순위 상관 {b['spearman_moisture_heating_value']}", 'f18')
add(15114951, '원전 호기별 계획예방정비 현황', '한국수력원자력', '②', '1차', '2011~2025', '정비 일수와 이용률 관계',
    f"상관 {n['corr_outage_days_vs_cf']}, 저이용 해 평균 정비 {n['low_cf_mean_outage_days']}일", 'f15')
add(15060801, '가동원전 호기별 계획예방정비 계획', '한국수력원자력', '②', '1차', '2025~2027 계획', '향후 정비 일정', f"{n['planned_outages']}건, 총 {n['planned_outage_days_total']:,.0f}일")
add(15074543, '연도별 원전 사고고장 현황', '한국원자력안전기술원', '②', '1차', '2020~2025 연별', '원전 사고·고장 추이', f"연 {min(n['incidents_by_year'].values())}~{max(n['incidents_by_year'].values())}건")
add(15061937, '보고대상사건 현황', '한국수력원자력', '②', '1차', '사건별 100건', '호기별 사건 빈도', f"월성3·4호기에 집중({list(n['reported_events_top_units'].values())[0]}·{list(n['reported_events_top_units'].values())[1]}건)")
add(15069337, '신재생 발전량 및 설비용량', '한국전력거래소', '③④', '1차', '2025 시간별 · 연료원별', '발전원별 예측 난이도 비교',
    f"어제 값 오차: 연료전지 {rb['연료전지']['dayahead_persistence_nRMSE']}% · 풍력 {rb['풍력']['dayahead_persistence_nRMSE']}%", 'f16')
add(15132422, '전국 태양광 풍력 제어횟수 및 제주 풍력 제어량', '한국전력거래소', '③', '1차', '2021~2026 상반기', '출력제어 증가 추이',
    f"육지 태양광 2024 {cu['days_by_year']['육지 태양광 출력제어횟수'].get('2024',0)}일 → 2025 {cu['days_by_year']['육지 태양광 출력제어횟수'].get('2025',0)}일", 'f17')
add(15152008, '육지 제주 통합 월별 계통한계가격', '한국전력거래소', '④', '1차', '2015~2025 월별', '예측 개선의 돈 가치(참고)',
    f"2024 평균 SMP {v['smp_2024_won_per_kWh']}원/kWh → 약 {v['value_100M_won']:,.0f}억 원 (단순 환산)")
add(15153657, '연료원별 일별 설비용량', '한국전력거래소', '④', '1차', '2024-12-31', '전원 구성 맥락', f"원자력 {cx['capacity_2024_MW']['원자력']:,} MW, 태양광 {cx['capacity_2024_MW']['태양광']:,} MW")
add(15086290, '신재생에너지 연도별 신규보급 현황', '한국에너지공단', '④', '1차', '2017~2024 연별', '신규 보급 추이', '2024년 태양광 신규 3,956 MW')
add(15140231, '발전소별 예방정비실적 정보', '한국중부발전', '②④', '1차', cx['komipo_planned_outages']['period'], '이상 알림과 정비 기록 대조 시도',
    f"{cx['komipo_planned_outages']['count']}건, 화력·복합만 있어 연료전지 대조 불가")
add(15136947, '설비 신뢰성 데이터', '한국서부발전', '④', '1차', '2022~ · 고장 기록 160건', '고장 유형 파악', f"상위 고장 유형: {list(cx['wp_failure_types_top'])[0]}")
# ── 2차 13종 (GPT 조사) ──
J, Hs = ws['장흥풍력'], ws['화순풍력']
add(15159034, '장흥풍력발전소 스카다 발전 정보', '한국서부발전', '③', '2차', J['period'] + ' 10분 · 6기', '풍속–출력 곡선, 풍속을 알 때의 오차',
    f"어제 값 {J['nRMSE_persistence_24h']}% → 실제 풍속+곡선 {J['nRMSE_curve_with_actual_wind']}%", 'f19')
top = sorted(Hs['stopped_by_unit'].items(), key=lambda x: -x[1])[:3]
add(15159036, '화순풍력발전소 스카다 발전 정보', '한국서부발전', '③', '2차', Hs['period'] + ' 시간별 · 8기', '호기별 정지 시간 비교',
    f"바람 충분한데 출력 0: {'·'.join(k+'호기' for k,_ in top)}에 집중", 'f19')
add(15043410, '한경풍력발전실적', '한국남부발전', '③', '2차', '2013~2026 시간별', '장기 풍력 예측 난이도', '어제 값 오차 연도별 22~38%')
add(15028181, '풍력발전기 전력 정보', '제주에너지공사', '③', '2차', jw['jeju_period'] + ' 일별 · 5개 단지', '단지끼리 비교', f"91일 참고 분석")
add(15165984, '기상정보 융합 한수원 태양광 시계열 발전정보', '한국수력원자력', '③④', '2차', '2023~2025 시간별 · 54곳', '발전소 단위 예측 검증',
    f"어제 값 {ks['nRMSE']['persistence']}% → 예보 항목 {ks['nRMSE']['예보 항목(기온·습도·풍속·강수)']}% → 실측 일사 {ks['nRMSE']['+ 실측 일조·일사']}%", 'f21')
add(15083316, '(발전공기업 표준) 발전실적 정보', '한국동서발전', '②', '2차', ew['period'] + ' 월별 · 호기별', '호기별 열효율 하락 알림',
    f"효율 2%p 하락 {ew['eff_drop_unit_months']} / {ew['judged_unit_months']:,} 호기·월, 상위는 연료전지")
add(15095396, '연료전지 발전실적', '한국남부발전', '②', '2차', '2018~2026 월별', '연료전지 장기 저하', f"{len(kf['declining_over_1pp_per_year'])}개 계열 연 1%p 넘게 하락", 'f22')
add(15118844, '에너지 사용현황', '충청남도개발공사', '①', '2차', '2016~2025 월별', '건물 지열 사용 계절 패턴', '여름·겨울 집중, 2021→2025 감소')
add(15164288, '외기온도에 따른 열생산량 대비 타사 수열량', '한국지역난방공사', '①', '2차', '일별 1,002일', '기온–열수요 관계', f"상관 {hm['kdhc_corr_temp_total_heat']}, 외부 수열 비중 {hm['kdhc_external_heat_share_pct']}%")
add(15161308, '제주발전기 연료원 시간대별 전력거래량', '한국전력거래소', '②③', '2차', '2010~2025 시간별', '제주 재생에너지 비중', f"{jf['renewable_share_pct_by_year']['2010']}% → {jf['renewable_share_pct_by_year']['2025']}%", 'f23')
add(15121931, '소수력 잠재 발전 가능량 데이터', '한국수자원공사', '③', '2차', '86개 유역', '유량–발전 관계', f"상관 {mi['smallhydro_corr_flow_power']}")
add(15149686, '공공하수처리시설 바이오가스 자체활용 현황', '경기도 부천시', '②', '2차', '2024 월별', '바이오가스 발전 활용', f"발전기 사용 {mi['biogas_generator_share_pct']}%")
add(15131797, '플랜트관리 예방정비 관리 실적', '한국지역난방공사', '④', '2차', '2023~2024', '정비 기록 형태 확인', f"{mi['kdhc_pm_records']}건 모두 '양호' → 대조용 정보 부족")
# ── 3차 12종 (GPT 조사) ──
add(15106338, '일별 발전실적 정보', '한국서부발전', '②', '3차', q['wp_daily_eff']['period'] + ' 일별 · 태안 10기', '석탄 호기 일별 효율 하락 알림',
    f"{q['wp_daily_eff']['alert_days']}일 / {q['wp_daily_eff']['judged_days']:,}일, 최다 태안 2호기")
ww = q['wp_wind']
add(15106292, '풍력 발전 현황', '한국서부발전', '③', '3차', '2017~2023 시간별', '풍력 단지별 예측 난이도', f"어제 값 오차 {min(x['persistence_nRMSE'] for x in ww.values())}~{max(x['persistence_nRMSE'] for x in ww.values())}%")
ss = q['seongsan_wind']; s1 = sorted(ss['low_days_by_unit'].items(), key=lambda x: -x[1])[:2]
add(15076400, '성산풍력 일평균 풍속데이터', '한국남부발전', '③', '3차', ss['period'] + ' · 10기', '같은 단지 호기끼리 풍속 비교',
    f"풍속이 단지보다 20% 이상 약한 날: {s1[0][0].replace('성산','')} {s1[0][1]}일, {s1[1][0].replace('성산','')} {s1[1][1]}일 (다른 호기는 대부분 30일 이하)", 'f25')
kz = q['kosep_solar']
add(15167614, '시간대별 태양광 실적 및 메타데이터', '한국남동발전', '③', '3차', kz['period'] + ' · 23곳', '같은 날 태양광끼리 비교', f"저하 후보 {kz['peer_low_days_total']:,}일(23곳 합)")
hp = q['hydro_pump']
add(15041895, '수력양수 발전량 및 이용률', '한국수력원자력', '③', '3차', '2024.12~2025.11 월별', '수력·양수 이용률', f"수력 {hp['hydro_cf_range'][0]}~{hp['hydro_cf_range'][1]}%, 양수 {hp['pumped_cf_range'][0]}~{hp['pumped_cf_range'][1]}%")
em = q['wp_emission']['taean_nox_per_GWh_by_year']
add(15099592, '대기오염물질 배출현황 및 발전량', '한국서부발전', '②④', '3차', '2002~2025 월별', '발전량당 NOx 추이', f"태안 2015 → 2025 발전량당 NOx {em['2015']/em['2025']:.0f}분의 1")
gh = q['kospo_ghg']['scope1_total_10kt_by_year']
add(15074207, '온실가스 배출량 정보', '한국남부발전', '④', '3차', '2015~2025 연별', '온실가스 직접배출 추이', f"정점 2018 {gh['2018']:,} → 2025 {gh['2025']:,} 만tCO₂")
kfu = q['komipo_fuel']['coal_stock_days_median_by_plant']
add(15155623, '발전소별 발전연료 입출고 및 재고 현황', '한국중부발전', '②', '3차', q['komipo_fuel']['period'] + ' 월별', '유연탄 재고 일수', ', '.join(f"{k} {v:.0f}일" for k, v in kfu.items()))
cw = q['kosep_cooling_water']
add(15144100, '온배수 수온 현황', '한국남동발전', '②', '3차', '2018~2024 월별', '냉각수 온도와 계절 효율', f"취수 온도 2월 {cw['intake_temp_by_month']['2']}℃ → 8월 {cw['intake_temp_by_month']['8']}℃")
sm = q['smp_fuel_2025']
add(15161908, 'SMP 결정 발전기 연료원', '한국전력거래소', '②④', '3차', '2025 시간별', '전기 가격을 정하는 연료', f"육지 LNG {sm['육지']['LNG']}%, 유연탄 {sm['육지']['유연탄']}% 시간", 'f24')
dm = q['demand_2025']
add(15065266, '시간별 전국 전력수요량', '한국전력거래소', '②', '3차', '2025 시간별', '수요 예측 난이도·최대전력 교차 확인',
    f"최대 {dm['peak_MW']:,.0f} MW(8/25, 수급 자료와 일치), 지난주 값 오차 {dm['persistence168_nRMSE_of_peak']}%")
bg = q['biogas_digester']
add(15151942, '혐기성 소화조 운영 데이터', '광주환경공단', '②', '3차', bg['period'] + ' 일별', '바이오가스 생산 이상 후보 알림', f"40% 이상 감소 {bg['alert_days']}일 / {bg['days']:,}일", 'f26')
assert len(C) == 50, len(C)
for i, c in enumerate(C, 1): c['no'] = i
json.dump(C, open('report/catalog.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
parts = {'①': '지열·수열', '②': '화력·원자력·바이오', '③': '태양광·풍력·수력', '④': '종합·모델'}
md = ['# 공공데이터 50종 목록', '', '> 발전원별 AI 예측·관리 시스템이 실제로 분석에 쓴 공공데이터포털(data.go.kr) 자료. 결과 값은 `results/results.json`에서 자동으로 채웠다(`python build/catalog.py`).', '',
      '| 묶음 | 개수 | 찾은 방법 | 분석 코드 |', '|---|---|---|---|',
      '| 기본 | 9 | 처음 받은 자료 | analyze.py, analyze_extra.py |', '| 1차 | 16 | Claude가 포털 검색 | analyze_public.py |',
      '| 2차 | 13 | GPT 웹 조사(검색 182회) | analyze_public2.py |', '| 3차 | 12 | GPT 웹 조사(검색 374회) | analyze_public3.py |', '']
for p, pn in parts.items():
    rows = [c for c in C if p in c['part']]
    md += [f'## 파트 {p} {pn} ({len(rows)}종)', '', '| # | 포털 번호 | 자료 | 기관 | 기간 | 쓴 곳 | 핵심 결과 | 그림 |', '|---|---|---|---|---|---|---|---|']
    md += [f"| {c['no']} | [{c['pk']}]({c['url']}) | {c['name']} | {c['org']} | {c['period']} | {c['use']} | {c['result']} | {c['fig']} |" for c in rows]
    md.append('')
md += ['※ 한 자료가 여러 파트에 걸치면 각 파트 표에 모두 나온다.', '',
       '## 받았지만 이번 분석에 넣지 않은 후보', '',
       '15065269 지역별 시간별 태양광·풍력(2025), 15150439 AWS 기상관측(삽당령 2024), 15124139 수열 용량예측 시나리오, 15108268 제주 제어량, 15037830 한국전력기술 신재생 생산, 15063796 행복도시 신재생 도입, 3075355 가연성폐기물 연료화시설, 15146840 울산 수소 열병합, 15052154 천연가스요금, 15118630 가스공사 ESS, 15084349 인천 송도 소각 운영, 15155898 남동발전 영흥 정비 정산, 15074542 시설별 원전 사고고장, 15159173 영천 농업기상, 15131649 동해 지붕태양광, 15044885 다목적댐 가뭄관리, 15161044 지역별 시간대별 전력거래량', '',
       '## 받을 수 없었던 것 (외부 포털·API 전용)', '', '15043494 기상청 단기예보, 3034018 원전 사고고장 DB, 15138940 원자재 가격, 15064530 수자원공사 발전소 운영, 15083252 표준수문DB, 15150737 2025 전력수급(EPSIS) 등']
open('report/데이터목록.md', 'w', encoding='utf-8').write('\n'.join(md) + '\n')
print('catalog', len(C), {p: sum(p in c['part'] for c in C) for p in parts})
