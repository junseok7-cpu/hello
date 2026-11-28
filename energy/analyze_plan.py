"""사용량(수요)에 따른 발전 계획 AI — 2025년 시간별 자료로 만든 시제품
흐름: ① 내일 전력수요 예측 ② 내일 태양광·풍력 예측 ③ 순수요(수요 − 태양광 − 풍력) = 나머지 발전소가 채울 양
      ④ 원자력(기저)을 먼저 놓고 나머지를 조절 가능한 발전(석탄·LNG 등)으로 채우는 계획 ⑤ 예측이 틀릴 때를 대비한 '대기 발전량' 계산
예측 시점: 전날 14시. 그때 알 수 있는 값만 사용(48시간 전·1주 전 값, 요일·시각·공휴일). 날씨 예보는 아직 없음(직접 받을 자료 목록 참고).
입력: data/public/15065266.csv(2025 시간별 전국 전력수요), 15069337.csv(2025 시간별 신재생 거래량·설비용량), 15152008.csv(월별 SMP)
관측 날씨 참고 실험: data/kma/asos_2025MM.csv, data/kma/stations.txt, 2024년 시도별 태양광 설비용량
출력: results/results.json 'plan' 키, figures/f27_plan_day.png, f28_plan_reserve.png, f29_plan_weather.png
"""
import io, json, os
import numpy as np, pandas as pd, lightgbm as lgb
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

for FONT in ['/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
             'C:/Windows/Fonts/malgun.ttf', '/System/Library/Fonts/AppleSDGothicNeo.ttc']:
    if os.path.exists(FONT):
        fm.fontManager.addfont(FONT); plt.rcParams['font.family'] = fm.FontProperties(fname=FONT).get_name(); break
plt.rcParams.update({'axes.unicode_minus': False, 'axes.spines.top': False, 'axes.spines.right': False, 'figure.dpi': 150})
INK, MUTED, MAIN, ACC, BAD, NUC = '#1d2b36', '#8a96a0', '#0f6e6a', '#e8a33d', '#c0392b', '#5b6fa8'
P, F, RJ = 'data/public/', 'figures/', 'results/results.json'
R = json.load(open(RJ, encoding='utf-8'))
def text(b):
    for e in ('utf-8-sig', 'cp949'):
        try: return b.decode(e)
        except UnicodeDecodeError: pass
def csv(pk):
    d = pd.read_csv(io.StringIO(text(open(f'{P}{pk}.csv', 'rb').read()))); d.columns = [c.strip() for c in d.columns]; return d
def num(s): return pd.to_numeric(s.astype(str).str.replace(',', '').str.strip(), errors='coerce')
def save(name): plt.tight_layout(); plt.savefig(F + name, dpi=200); plt.close()

# ── 자료: 시간별 수요, 태양광, 풍력 (MW = 1시간 MWh) ──
d = csv(15065266).dropna(subset=['날짜']); d['d'] = pd.to_datetime(d['날짜'], errors='coerce'); d = d.dropna(subset=['d'])
h = d.melt(id_vars=['d'], value_vars=[f'{i}시' for i in range(1, 25)], var_name='h', value_name='demand')
h['t'] = h.d + pd.to_timedelta(h.h.str.replace('시', '').astype(int) - 1, unit='h'); h['demand'] = num(h.demand)
df = h.set_index('t')[['demand']].sort_index()
r = csv(15069337); r['t'] = pd.to_datetime(r['거래일자']) + pd.to_timedelta(num(r['시간'].str[:2]) - 1, unit='h')
for k, col in [('태양광', 'solar'), ('풍력', 'wind')]:
    g = r[r['연료원'] == k].groupby('t')[['전력거래량(MWh)', '설비용량']].sum()
    df[col] = num(g['전력거래량(MWh)']).reindex(df.index); df[col + '_cap'] = num(g['설비용량']).reindex(df.index)
df = df.asfreq('h')
# 급전가능 재생에너지(대형 풍력 등)는 연중 분류가 바뀌어 순수요 계산에서 제외 — 시장 거래 태양광·풍력만 사용
df['net'] = df.demand - df.solar.fillna(0) - df.wind.fillna(0)

# ── 기상청 ASOS: 시도별 관측소 평균을 전국 특징으로 집계 ──
REGION = dict(zip(
    '11 26 27 28 29 30 31 36 41 42 51 43 44 45 52 46 47 48 50'.split(),
    '서울 부산 대구 인천 광주 대전 울산 세종 경기 강원 강원 충북 충남 전북 전북 전남 경북 경남 제주'.split(),
))
SOLAR_WEATHER = ['si', 'ss', 'ca_tot', 'ta', 'hm', 'rn']
stations = pd.read_csv(io.StringIO(text(open('data/kma/stations.txt', 'rb').read())),
                       sep=r'\s+', comment='#', header=None, usecols=[0, 13],
                       names=['stn', 'law_id'], dtype={'law_id': str})
regions = stations.set_index('stn').law_id.str[:2].map(REGION)
weather = pd.concat([pd.read_csv(f'data/kma/asos_2025{month:02d}.csv', dtype={'tm': str})
                     for month in range(1, 13)], ignore_index=True)
weather['t'] = pd.to_datetime(weather.tm, format='%Y%m%d%H%M')  # 발전 자료도 KST
weather['region'] = weather.stn.map(regions)
weather_cols = SOLAR_WEATHER + ['ws']
weather[weather_cols] = weather[weather_cols].replace([-9, -99, -999, -9999], np.nan)
regional = weather.groupby(['t', 'region'])[weather_cols].mean()
weights = pd.Series({region: history[-1] for region, history in R['D']['cap_growth'].items()})
national = regional.groupby(level='t')[['ws', 'ta', 'hm']].mean().add_suffix('_national')
for col in SOLAR_WEATHER:
    hourly = regional[col].unstack('region').reindex(columns=weights.index)
    # 매 시각 관측값이 있는 시도의 설비용량 합을 분모로 사용한다.
    national[col + '_weighted'] = hourly.mul(weights).sum(axis=1, min_count=1) / hourly.notna().mul(weights).sum(axis=1)

# tm은 직전 1시간의 끝이고 발전 t는 시작이다. 시험 월을 제외한 공통 관측
# 시각에서 태양광과 일사의 피어슨 상관을 비교해 tm 그대로와 tm - 1시간 중 선택한다.
irradiance = national.si_weighted
alignment = pd.concat({'solar': df.solar, 0: irradiance,
                       -1: irradiance.shift(-1, freq='h')}, axis=1).loc[:'2025-08-31'].dropna()
correlations = alignment[[0, -1]].corrwith(alignment.solar)
weather_shift = int(correlations.idxmax())
national.index += pd.Timedelta(hours=weather_shift)
df = df.join(national)

# ── 특징(전날 14시에 알 수 있는 것만) ──
HOL = pd.to_datetime(['2025-01-01', '2025-01-27', '2025-01-28', '2025-01-29', '2025-01-30', '2025-03-01', '2025-03-03', '2025-05-05', '2025-05-06',
                      '2025-06-03', '2025-06-06', '2025-08-15', '2025-10-03', '2025-10-05', '2025-10-06', '2025-10-07', '2025-10-08', '2025-10-09', '2025-12-25'])
df['hour'], df['dow'], df['month'] = df.index.hour, df.index.dayofweek, df.index.month
df['holiday'] = df.index.normalize().isin(HOL).astype(int)
df['off'] = ((df.dow >= 5) | (df.holiday == 1)).astype(int)                # 쉬는 날
for c in ['demand', 'solar', 'wind']:
    df[f'{c}_l48'], df[f'{c}_l168'] = df[c].shift(48), df[c].shift(168)
    df[f'{c}_d2mean'] = df[c].rolling(24).mean().shift(48)                 # 이틀 전 하루 평균
# 수준(level)은 최근 값에서 가져오고, AI는 "이틀 전 하루 평균 대비 비율"(시간대·요일·공휴일 패턴)을 배운다
for c in ['demand', 'solar', 'wind']:
    base = df[f'{c}_d2mean'].replace(0, np.nan)
    df[f'{c}_r'] = df[c] / base                                             # 학습 목표: 비율
    df[f'{c}_r48'], df[f'{c}_r168'] = df[f'{c}_l48'] / base, df[f'{c}_l168'] / base
    df[f'{c}_trend'] = base / df[c].rolling(24).mean().shift(168)          # 이틀 전 평균 ÷ 일주일 전 평균
FE = {'demand': ['hour', 'dow', 'holiday', 'off', 'demand_r48', 'demand_r168', 'demand_trend'],
      'solar': ['hour', 'solar_r48', 'solar_r168', 'solar_trend'],
      'wind': ['hour', 'wind_r48', 'wind_r168', 'wind_trend']}
START, TE = pd.Timestamp('2025-01-09'), df.index >= '2025-09-01'
WEATHER_FE = {
    'demand': ['ta_national', 'hm_national'],
    'solar': ['si_weighted', 'ss_weighted', 'ca_tot_weighted', 'ta_weighted'],
    'wind': ['ws_national'],
}

def predict(features, suffix):
    for c, cols in features.items():
        df[c + suffix] = np.nan
        for m0 in pd.date_range('2025-09-01', '2025-12-01', freq='MS'):
            # 날씨 결측은 LightGBM이 처리하고, 두 조건의 학습·시험 시각은 유지한다.
            tr = (df.index >= START) & (df.index < m0 - pd.Timedelta(days=1)) & df[FE[c] + [c + '_r']].notna().all(axis=1) & np.isfinite(df[c + '_r'])
            te = (df.index >= m0) & (df.index < m0 + pd.offsets.MonthBegin(1))
            m = lgb.LGBMRegressor(n_estimators=500, learning_rate=0.03, num_leaves=31, min_child_samples=40, verbose=-1, random_state=0).fit(df.loc[tr, cols], df.loc[tr, c + '_r'])
            df.loc[te, c + suffix] = (pd.Series(m.predict(df.loc[te, cols]), index=df.index[te]) * df.loc[te, f'{c}_d2mean']).clip(lower=0)
    df['net' + suffix] = df['demand' + suffix] - df['solar' + suffix] - df['wind' + suffix]

predict(FE, '_ai')
predict({c: cols + WEATHER_FE[c] for c, cols in FE.items()}, '_weather')
for c in FE:
    df[c + '_base'] = df[c + '_l168']  # 지난주 같은 요일·시각
df['net_base'] = df.demand_base - df.solar_base - df.wind_base
ev = df[TE].dropna(subset=['net', 'net_ai', 'net_base'])

def errs(a, f):
    e = f - a; return dict(MAE_MW=round(float(e.abs().mean())), RMSE_MW=round(float(np.sqrt((e ** 2).mean()))),
                           MAPE_pct=round(float((e.abs() / a).mean() * 100), 2),
                           reserve_P95_MW=round(float(e.abs().quantile(0.95))),            # 95% 시간을 버티려면 대기해야 하는 양
                           over_GWh=round(float(e.clip(lower=0).sum() / 1000), 1),        # 예측이 실제보다 많아 '괜히 준비한' 양
                           under_GWh=round(float((-e).clip(lower=0).sum() / 1000), 1))     # 예측이 모자라 '급히 채워야 한' 양
def summarize(suffix):
    out = dict(period_train='2025-01-09부터 매달 직전까지 (매달 다시 학습)', period_test='2025-09-01~2025-12-31', test_hours=int(len(ev)),
               demand={'AI': errs(ev.demand, ev['demand' + suffix]), '지난주 같은 시각': errs(ev.demand, ev.demand_base)},
               net={'AI': errs(ev.net, ev['net' + suffix]), '지난주 같은 시각': errs(ev.net, ev.net_base)})
    for c in ['solar', 'wind']:                                                      # 태양광·풍력은 0인 시간이 있어 MAPE 대신 설비용량 대비 오차
        e1, e2 = ev[c + suffix] - ev[c], ev[c + '_base'] - ev[c]; cap = ev[c + '_cap']
        out[c] = {'AI_nMAE_pct': round(float((e1.abs() / cap).mean() * 100), 2), '지난주_nMAE_pct': round(float((e2.abs() / cap).mean() * 100), 2)}
    na, nb = out['net']['AI'], out['net']['지난주 같은 시각']
    out['reserve_saving_MW'] = nb['reserve_P95_MW'] - na['reserve_P95_MW']
    out['over_saving_GWh'] = round(nb['over_GWh'] - na['over_GWh'], 1)
    offm = ev.off == 1                                                               # 쉬는 날(주말·공휴일)만 따로
    out['net_offday'] = {'AI': errs(ev.net[offm], ev['net' + suffix][offm]), '지난주 같은 시각': errs(ev.net[offm], ev.net_base[offm])}
    return out

out = summarize('_ai')
with_weather = summarize('_weather')
with_weather['alignment'] = dict(
    shift_hours=weather_shift,
    solar_irradiance_corr_unshifted=round(float(correlations[0]), 4),
    solar_irradiance_corr_minus_1h=round(float(correlations[-1]), 4),
)
with_weather['caution'] = ('예측 대상 시각의 기상청 실제 관측 날씨를 넣은 참고 상한이다. '
                           '전날에는 이 관측값을 알 수 없으며 실제 예보에는 오차가 있다.')
out['with_weather'] = with_weather
na, nb = out['net']['AI'], out['net']['지난주 같은 시각']

# ── 발전 계획: 원자력(기저) 먼저 + 나머지 조절 가능한 발전 ──
nuc_cap = R['public']['context']['capacity_2024_MW']['원자력']                 # 2024-12-31 설비용량
nuc_cf = R['nuclear']['fleet_median_cf']['2025'] / 100                         # 2025 호기별 이용률 중앙값
nuc = nuc_cap * nuc_cf
ev = ev.assign(flex_plan=(ev.net_ai - nuc).clip(lower=0), flex_need=(ev.net - nuc).clip(lower=0))
out['plan'] = dict(nuclear_MW=round(nuc), nuclear_basis=f'원자력 설비 {nuc_cap:,} MW × 2025 이용률 중앙값 {nuc_cf*100:.1f}% (가정)',
                   flex_plan_mean_MW=round(float(ev.flex_plan.mean())), flex_plan_max_MW=round(float(ev.flex_plan.max())),
                   flex_need_mean_MW=round(float(ev.flex_need.mean())))
smp = csv(15152008); smp['y'] = num(smp['년도']); s25 = float(num(smp[smp.y == 2025]['통합계통한계가격']).mean())
out['smp_2025_mean_won_per_kWh'] = round(s25, 1)
out['over_saving_value_100M_won'] = round(out['over_saving_GWh'] * 1e6 * s25 / 1e8, 1)
out['caution'] = ('날씨 예보 없이 과거 값·요일·공휴일만 쓴 시제품. 태양광·풍력은 시장 거래분만 포함(자가소비 등 제외). '
                  '원자력 기저량은 이용률 중앙값을 쓴 가정이며 실제 급전 계획(발전기별 비용·제약)은 반영하지 않음. 돈 환산은 SMP 단순평균을 곱한 참고값.')

# ── 그림 1: 예시 하루 (시험 기간 중 쉬는 날 다음 평일) ──
days = sorted({t.normalize() for t in ev.index})
day = next((dd for dd in days if ev.loc[dd:dd + pd.Timedelta(hours=23), 'off'].max() == 0 and (dd - pd.Timedelta(days=1)) in days
            and ev.loc[dd - pd.Timedelta(days=1):dd - pd.Timedelta(hours=1), 'off'].max() == 1 and len(ev.loc[dd:dd + pd.Timedelta(hours=23)]) == 24), days[0])
x = ev.loc[day: day + pd.Timedelta(hours=23)]
fig, axs = plt.subplots(1, 2, figsize=(12, 4.2))
hh = x.index.hour + 1
axs[0].fill_between(hh, 0, nuc, color=NUC, alpha=.35, step='mid', label='원자력(기저, 가정)')
axs[0].fill_between(hh, nuc, x.net_ai, color=MAIN, alpha=.30, step='mid', label='조절 발전 계획(석탄·LNG 등)')
axs[0].fill_between(hh, x.net_ai, x.demand_ai, color=ACC, alpha=.45, step='mid', label='태양광·풍력 예측')
axs[0].plot(hh, x.demand, color=INK, lw=2, label='실제 수요'); axs[0].plot(hh, x.demand_ai, color=INK, lw=1.2, ls='--', label='AI 수요 예측')
axs[0].set_xlabel('시각'); axs[0].set_ylabel('MW'); axs[0].set_title(f'{day:%Y-%m-%d} 발전 계획 (전날 14시 작성)', loc='left'); axs[0].legend(frameon=False, fontsize=7.5, loc='lower right')
axs[0].set_ylim(0, max(x.demand.max(), x.demand_ai.max()) * 1.08)
axs[1].plot(hh, x.net, color=INK, lw=2, label='실제 순수요'); axs[1].plot(hh, x.net_ai, color=MAIN, lw=1.8, label='AI 예측')
axs[1].plot(hh, x.net_base, color=BAD, lw=1.4, ls='--', label='지난주 같은 시각')
axs[1].set_xlabel('시각'); axs[1].set_ylabel('MW'); axs[1].set_title('순수요 = 수요 - 태양광 - 풍력', loc='left'); axs[1].legend(frameon=False, fontsize=8)
save('f27_plan_day.png'); out['example_day'] = str(day.date())

# ── 그림 2: 대기해야 하는 발전량 비교 ──
fig, axs = plt.subplots(1, 2, figsize=(11, 3.8))
lab = ['지난주 같은 시각', 'AI']
v = [nb['reserve_P95_MW'], na['reserve_P95_MW']]
axs[0].bar(lab, v, color=[MUTED, MAIN], width=.55)
for i, y in enumerate(v): axs[0].text(i, y + max(v) * .02, f'{y:,} MW', ha='center', fontsize=10)
axs[0].set_title('예측이 틀릴 때를 대비해 대기할 발전량\n(시간의 95%를 버티는 양)', loc='left', fontsize=10); axs[0].set_ylabel('MW')
v2 = [nb['over_GWh'], na['over_GWh']]
axs[1].bar(lab, v2, color=[MUTED, MAIN], width=.55)
for i, y in enumerate(v2): axs[1].text(i, y + max(v2) * .02, f'{y:,.0f} GWh', ha='center', fontsize=10)
axs[1].set_title('실제보다 많이 준비한 전력량\n(2025년 9~12월 합계)', loc='left', fontsize=10); axs[1].set_ylabel('GWh')
save('f28_plan_reserve.png')

# ── 그림 3: 같은 시험 시간에서 날씨 입력 효과 비교 ──
fig, axs = plt.subplots(1, 2, figsize=(12, 4))
labels = ['지난주 같은 시각', 'AI(날씨 없음)', 'AI(관측 날씨, 참고)']
colors = [MUTED, MAIN, NUC]
reserve = [nb['reserve_P95_MW'], na['reserve_P95_MW'], with_weather['net']['AI']['reserve_P95_MW']]
bars = axs[0].bar(labels, reserve, color=colors, width=.65)
axs[0].bar_label(bars, labels=[f'{v:,}' for v in reserve], padding=3)
axs[0].set_ylim(0, max(reserve) * 1.15)
axs[0].set_title('대기 발전량 (P95)', loc='left')
axs[0].set_ylabel('MW')

sources = ['solar', 'wind']
xpos = np.arange(len(sources))
errors = [
    [out[c]['지난주_nMAE_pct'] for c in sources],
    [out[c]['AI_nMAE_pct'] for c in sources],
    [with_weather[c]['AI_nMAE_pct'] for c in sources],
]
for offset, values, color, label in zip([-0.24, 0, 0.24], errors, colors, labels):
    bars = axs[1].bar(xpos + offset, values, width=.22, color=color, label=label)
    axs[1].bar_label(bars, fmt='%.2f', padding=3)
axs[1].set_ylim(0, np.max(errors) * 1.35)
axs[1].set_xticks(xpos, ['태양광', '풍력'])
axs[1].set_title('태양광·풍력 예측 오차', loc='left')
axs[1].set_ylabel('설비용량 대비 평균 절대 오차 (%)')
axs[1].legend(frameon=False, fontsize=8, ncol=3, loc='upper center')
save('f29_plan_weather.png')

R['plan'] = out
def clean(o):
    if isinstance(o, dict): return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [clean(v) for v in o]
    if isinstance(o, float) and not np.isfinite(o): return None
    if isinstance(o, np.generic): return clean(o.item())
    return o
json.dump(clean(R), open(RJ, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str, allow_nan=False)
print(json.dumps(clean(out), ensure_ascii=False, indent=1))
