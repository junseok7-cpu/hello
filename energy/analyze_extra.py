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
dm['demand_GWh'] = dm[hrs].sum(axis=1) / 1000          # MW × 1h → GWh
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
j = j.dropna()
tr, te = j[j.index.year <= 2020], j[j.index.year == 2021]

FEAT = {  # 관측 수요: 당일 실제 수요를 넣음 → 상한선 / 전날 수요: 당일 정보 없이 하루 전에 할 수 있는 예측
    '관측 수요 입력(상한선)': ['demand_GWh', 'demand_max_GW', 'msin', 'mcos', 'lag1', 'lag7'] + DOW,
    '전날 수요만 입력(현실 조건)': ['dem_lag1', 'demmax_lag1', 'msin', 'mcos', 'lag1', 'lag7'] + DOW,
}
mean_te = float(te.LNG.mean())
def metr(y, p):
    mae, rmse = float(np.mean(np.abs(y - p))), float(np.sqrt(np.mean((y - p) ** 2)))
    return dict(MAE_GWh=round(mae, 2), RMSE_GWh=round(rmse, 2), nMAE=round(mae / mean_te * 100, 2), nRMSE=round(rmse / mean_te * 100, 2))
pers = metr(te.LNG, te.lag1); pers['Skill'] = 0.0
L = dict(train='2018~2020', test='2021', test_days=int(len(te)), test_mean_GWh=round(mean_te, 1),
         note='Skill = 1 - RMSE/RMSE(어제 값). nMAE·nRMSE는 2021년 일평균 LNG 발전량 대비 %.',
         models={'어제 값(Persistence)': pers}, pred={})
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
k1 = '선형회귀 · 관측 수요 입력(상한선)'; k2 = '선형회귀 · 전날 수요만 입력(현실 조건)'
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

def detect(g, abs_drop=0.15):  # analyze.py 연료전지 블록과 같은 규칙: 과거 28일 중앙값 대비 3σ(MAD) 이탈 + 설비용량 15%p 이상 하락
    g = g.sort_values('d').set_index('d')
    base = g.cf.shift(1).rolling(28, min_periods=14).median()
    mad = (g.cf - base).abs().shift(1).rolling(90, min_periods=30).median() * 1.4826
    z = (g.cf - base) / mad.replace(0, np.nan)
    alert = (z < -3) & ((base - g.cf) >= abs_drop)
    zero = (g.cf <= 0.001)
    streak = zero.groupby((~zero).cumsum()).cumsum().max() if len(g) else 0
    return dict(days=int(len(g)), cf_median=round(float(g.cf.median()), 3), alerts=int(alert.sum()),
                events=int((alert & ~alert.shift(1, fill_value=False)).sum()),
                zero_days=int(zero.sum()), longest_zero_streak=int(streak))
W = {}
for (t, name), g in k[k.type != '기타'].groupby(['type', '발전설비']):
    W[name] = dict(type=t, **detect(g))
R['wind_hydro'] = dict(rule='과거 28일 중앙값 대비 3σ(MAD) 이탈 + 설비용량 15%p 이상 하락 (연료전지와 같은 규칙)',
                       caution='풍력은 평소 이용률이 10% 안팎이라 15%p 하락 조건이 거의 성립하지 않는다. 0건은 "이상 없음"이 아니라 이 규칙이 풍력에 맞지 않는다는 뜻이다. 소수력은 강수에 따라 출력이 크게 바뀌어 알림 일부는 가뭄·갈수기일 수 있다.',
                       plants=W)
print('wind_hydro', json.dumps(W, ensure_ascii=False, indent=1))

fig, ax = plt.subplots(figsize=(8, 3.6))
names = list(W); vals = [W[n]['alerts'] for n in names]
cols = [ACC if W[n]['type'] == '풍력' else MAIN for n in names]
b = ax.barh(names[::-1], vals[::-1], color=cols[::-1])
for bb, n in zip(b, names[::-1]):
    ax.text(bb.get_width() + .5, bb.get_y() + bb.get_height() / 2, f"{W[n]['alerts']}일 ({W[n]['events']}구간) · 중앙 이용률 {W[n]['cf_median']*100:.0f}%", va='center', fontsize=8.5, color=INK)
ax.set_xlabel('이상 후보 알림 일수'); ax.set_xlim(0, max(vals + [1]) * 1.9); ax.set_title('풍력(주황)·소수력(청록) 설비별 이상 후보 알림', loc='left')
save('f12_wind_hydro.png')

json.dump(R, open(RJ, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
print('wrote', RJ, '+ figures f11, f12')
