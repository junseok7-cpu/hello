"""추가 분석 — 화력 LNG 일별 예측(lng_pred), 풍력·소수력 이상 후보 알림(wind_hydro)
입력: data/fuel_daily_region_2018_2022.csv, data/demand_hourly_2017_2021.csv, data/komipo_plants_daily_2023_2026.csv
출력: results/results.json에 lng_pred·wind_hydro 키를 추가(기존 키는 그대로), figures/f11_lng_pred.png, f12_wind_hydro.png
실행: python analyze.py 다음에 python analyze_extra.py (수 초)
"""
import json, os, sys
import numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import HistGradientBoostingRegressor

# 한글 폰트: 있는 것 중 첫 번째
for FONT in ['/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
             'C:/Windows/Fonts/malgun.ttf', '/System/Library/Fonts/AppleSDGothicNeo.ttc']:
    if os.path.exists(FONT):
        fm.fontManager.addfont(FONT); plt.rcParams['font.family'] = fm.FontProperties(fname=FONT).get_name(); break
plt.rcParams.update({'axes.unicode_minus': False, 'axes.spines.top': False, 'axes.spines.right': False, 'figure.dpi': 150})
INK, MUTED, MAIN, ACC, BAD = '#1d2b36', '#8a96a0', '#0f6e6a', '#e8a33d', '#c0392b'
D = sys.argv[1] if len(sys.argv) > 1 else 'data/'
RJ, F = 'results/results.json', 'figures/'
R = json.load(open(RJ, encoding='utf-8')) if os.path.exists(RJ) else {}
def save(name): plt.tight_layout(); plt.savefig(F + name, dpi=200); plt.close()

# ───────────────────────── 1. 화력 LNG 일별 발전량 예측 ─────────────────────────
dm = pd.read_csv(D + 'demand_hourly_2017_2021.csv'); dm['d'] = pd.to_datetime(dm['거래일'])
hrs = [f'{i}시' for i in range(1, 25)]
dm['demand_GWh'] = dm[hrs].sum(axis=1, min_count=24) / 1000   # 24시간이 다 있는 날만          # MW × 1h → GWh
dm['demand_max_GW'] = dm[hrs].max(axis=1) / 1000
fu = pd.read_csv(D + 'fuel_daily_region_2018_2022.csv'); fu.columns = [c.strip() for c in fu.columns]
fu['d'] = pd.to_datetime(fu['거래일자'])
lng = fu[fu['연료원'] == 'LNG'].groupby('d')['발전량(MWh)'].sum() / 1000
j = pd.DataFrame({'LNG': lng}).join(dm.set_index('d')[['demand_GWh', 'demand_max_GW']], how='inner').sort_index()
j = j.asfreq('D')                                       # 빠진 날이 있으면 NaN으로 드러나게
j['lag1'] = j.LNG.shift(1); j['lag7'] = j.LNG.shift(7)
j['dem_lag1'] = j.demand_GWh.shift(1); j['demmax_lag1'] = j.demand_max_GW.shift(1)
j['msin'] = np.sin(2 * np.pi * j.index.month / 12); j['mcos'] = np.cos(2 * np.pi * j.index.month / 12)
dow = pd.get_dummies(j.index.dayofweek, prefix='dow', drop_first=True).astype(float); dow.index = j.index
j = j.join(dow); DOW = list(dow.columns)
L_missing = int(j[['LNG', 'demand_GWh']].isna().any(axis=1).sum())   # LNG나 수요가 빠진 날 수(날짜 기준, 평가에서 제외됨)
j = j.dropna()
tr, te = j[j.index.year <= 2020], j[j.index.year == 2021]

FEAT = {  # 수요 없음 = 수요 피처의 기여 확인용 / 관측 수요 = 당일 실제 수요(사후 참고) / 전날 수요 = 하루 전에 할 수 있는 현실 조건
    '수요 없음(달력+과거 LNG)': ['msin', 'mcos', 'lag1', 'lag7'] + DOW,
    '관측 수요 입력(사후 참고)': ['demand_GWh', 'demand_max_GW', 'msin', 'mcos', 'lag1', 'lag7'] + DOW,
    '전날 수요만 입력(현실 조건)': ['dem_lag1', 'demmax_lag1', 'msin', 'mcos', 'lag1', 'lag7'] + DOW,
}
mean_te = float(te.LNG.mean())
def metr(y, p):
    mae, rmse = float(np.mean(np.abs(y - p))), float(np.sqrt(np.mean((y - p) ** 2)))
    return dict(MAE_GWh=round(mae, 2), RMSE_GWh=round(rmse, 2), nMAE=round(mae / mean_te * 100, 2), nRMSE=round(rmse / mean_te * 100, 2))
pers = metr(te.LNG, te.lag1); pers['Skill'] = 0.0
wk = metr(te.LNG, te.lag7); wk['Skill'] = round(1 - wk['RMSE_GWh'] / pers['RMSE_GWh'], 3)
L = dict(train='2018~2020', test='2021', test_days=int(len(te)), test_mean_GWh=round(mean_te, 1), missing_days=L_missing,
         note='Skill = 1 - RMSE/RMSE(어제 값). nMAE·nRMSE는 2021년 일평균 LNG 발전량 대비 %.',
         models={'어제 값(Persistence)': pers, '전주 같은 요일 값': wk}, pred={},
         caution='당일 관측 수요 조건은 수요가 하루가 끝나야 확정되므로 사후 참고 실험이다. 전날 수요 조건은 전날 수요·LNG 집계가 예측 발행 시각까지 확보된다고 가정한다. 시험은 2021년 한 해뿐이다.')
for cond, cols in FEAT.items():
    for mname, m in [('선형회귀', LinearRegression()), ('GBDT', HistGradientBoostingRegressor(random_state=0, max_iter=300, learning_rate=0.05))]:
        p = m.fit(tr[cols], tr.LNG).predict(te[cols])
        r = metr(te.LNG, p); r['Skill'] = round(1 - r['RMSE_GWh'] / pers['RMSE_GWh'], 3)
        L['models'][f'{mname} · {cond}'] = r; L['pred'][f'{mname} · {cond}'] = p
R['lng_pred'] = {k: v for k, v in L.items() if k != 'pred'}
print('lng_pred', json.dumps(R['lng_pred']['models'], ensure_ascii=False, indent=1))

fig, ax = plt.subplots(figsize=(10, 3.8))
ax.plot(te.index, te.LNG, color=INK, lw=1.2, label='실제 LNG 발전량')
ax.plot(te.index, te.lag1, color=MUTED, lw=.8, ls='--', label='어제 값')
k1 = '선형회귀 · 관측 수요 입력(사후 참고)'; k2 = '선형회귀 · 전날 수요만 입력(현실 조건)'
ax.plot(te.index, L['pred'][k1], color=MAIN, lw=1.4, label=f"선형회귀·관측 수요 (Skill {L['models'][k1]['Skill']:.2f})")
ax.plot(te.index, L['pred'][k2], color=ACC, lw=1.2, label=f"선형회귀·전날 수요 (Skill {L['models'][k2]['Skill']:.2f})")
ax.set_ylabel('GWh/일'); ax.set_title('2021년 일별 LNG 발전량 — 실제와 예측', loc='left'); ax.legend(frameon=False, fontsize=8.5, ncol=2)
save('f11_lng_pred.png')

# ───────────────────────── 2. 풍력·소수력 이상 후보 알림 ─────────────────────────
k = pd.read_csv(D + 'komipo_plants_daily_2023_2026.csv'); k.columns = [c.strip() for c in k.columns]
k['d'] = pd.to_datetime(k['연월일'])
bad = (k.d >= '2025-01-01') & (k.d <= '2025-06-30')
k.loc[bad, '발전량'] = k.loc[bad, '발전량'] / 1000                       # analyze.py와 같은 보정
k.loc[k['발전설비'] == '인천연료전지', '설비용량'] = 31680
k['설비용량'] = k.groupby('발전설비')['설비용량'].transform('max')
k = k[~k['발전설비'].str.contains('ESS')].drop_duplicates(['연월일', '발전설비'])
k['type'] = np.select([k['발전설비'].str.contains('풍력'), k['발전설비'].str.contains('소수력')], ['풍력', '소수력'], '기타')
k['cf'] = k['발전량'] / (k['설비용량'] * 24)

def detect(g, abs_drop=0.15, rel_drop=0.5, min_base=0.03):
    """연료전지 규칙(과거 28일 중앙값 대비 3σ(MAD) 이탈 + 설비용량 15%p 하락)과
    상대 하락 규칙(28일 중앙값의 50% 이상 하락, 기준 이용률 3% 이상일 때만)을 함께 계산한다.
    날짜는 달력 기준으로 다시 맞춰 빠진 날이 연속 구간을 잇지 않게 한다."""
    g = g.sort_values('d').set_index('d')
    obs = len(g)
    if obs < 30:
        return dict(days=obs, judgeable=False, note='관측 30일 미만 — 판정 불가')
    g = g.asfreq('D')                                     # 빠진 날은 NaN
    cf = g.cf
    base = cf.shift(1).rolling(28, min_periods=14).median()
    mad = (cf - base).abs().shift(1).rolling(90, min_periods=30).median() * 1.4826
    z = (cf - base) / mad.replace(0, np.nan)
    a_abs = ((z < -3) & ((base - cf) >= abs_drop)).fillna(False)
    a_rel = ((z < -3) & (base >= min_base) & ((base - cf) / base >= rel_drop)).fillna(False)
    ev = lambda a: int((a & ~a.shift(1, fill_value=False)).sum())
    zero = (cf.abs() <= 0.001)                            # 결측(NaN)은 False → 연속 구간이 끊김
    streak = int(zero.groupby((~zero).cumsum()).cumsum().max())
    return dict(days=obs, missing_days=int(cf.isna().sum()), judgeable=True, cf_median=round(float(cf.median()), 3),
                alerts=int(a_abs.sum()), events=ev(a_abs),            # 연료전지 규칙: 알림 일수 / 구간 수
                alerts_rel=int(a_rel.sum()), events_rel=ev(a_rel),    # 상대 하락 규칙
                zero_days=int(zero.sum()), longest_zero_streak=streak)
W = {}
for (t, name), g in k[k.type != '기타'].groupby(['type', '발전설비']):
    W[name] = dict(type=t, **detect(g))
R['wind_hydro'] = dict(rule='alerts/events: 과거 28일 중앙값 대비 3σ(MAD) 이탈 + 설비용량 15%p 이상 하락(연료전지와 같은 규칙). alerts_rel/events_rel: 3σ 이탈 + 기준 대비 50% 이상 하락(기준 이용률 3% 이상). alerts는 일수, events는 구간 수. 날짜는 달력 기준.',
                       caution='풍력은 평소 이용률이 10% 안팎이라 15%p 하락 조건이 거의 성립하지 않는다. 0건은 "이상 없음"이 아니라 이 규칙이 풍력에 맞지 않는다는 뜻이다. 소수력은 강수에 따라 출력이 크게 바뀌어 알림 일부는 가뭄·갈수기일 수 있다.',
                       plants=W)
print('wind_hydro', json.dumps(W, ensure_ascii=False, indent=1))

fig, ax = plt.subplots(figsize=(8, 3.8))
names = [n for n in W if W[n].get('judgeable')]; y = np.arange(len(names))
va = [W[n]['alerts'] for n in names]; vr = [W[n]['alerts_rel'] for n in names]
ax.barh(y + .2, va, .4, color=MAIN, label='연료전지 규칙(15%p 하락)'); ax.barh(y - .2, vr, .4, color=ACC, label='상대 하락 규칙(50% 하락)')
for i, n in enumerate(names):
    ax.text(max(va[i], vr[i]) + .5, i, f"{W[n]['type']} · 중앙 이용률 {W[n]['cf_median']*100:.0f}%", va='center', fontsize=8.5, color=INK)
ax.set_yticks(y, names); ax.invert_yaxis(); ax.set_xlabel('이상 후보 알림 일수'); ax.set_xlim(0, max(va + vr + [1]) * 1.8)
skip = [n for n in W if not W[n].get('judgeable')]
ax.set_title('풍력·소수력 설비별 이상 후보 알림' + (f"  (판정 불가: {', '.join(skip)})" if skip else ''), loc='left', fontsize=10)
ax.legend(frameon=False, fontsize=8.5, loc='lower right')
save('f12_wind_hydro.png')

json.dump(R, open(RJ, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
print('wrote', RJ, '+ figures f11, f12')
