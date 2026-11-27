"""발전원별 AI 예측·관리 시스템 — 분석 파이프라인
입력: data/*.csv (UTF-8 변환본)   출력: results/results.json, figures/*.png
실행: python analyze.py
"""
import json, time
import numpy as np, pandas as pd, lightgbm as lgb
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from sklearn.linear_model import LinearRegression

FONT = '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc'
fm.fontManager.addfont(FONT)
plt.rcParams.update({'font.family': fm.FontProperties(fname=FONT).get_name(), 'axes.unicode_minus': False,
                     'axes.spines.top': False, 'axes.spines.right': False, 'figure.dpi': 150})
INK, MUTED, MAIN, ACC, OK, BAD = '#1d2b36', '#8a96a0', '#0f6e6a', '#e8a33d', '#2f7d4f', '#c0392b'
D, R, F = 'data/', {}, 'figures/'
T0 = time.time()
def log(*a): print(f'[{time.time()-T0:6.0f}s]', *a, flush=True)
def save(name): plt.tight_layout(); plt.savefig(F + name, dpi=200); plt.close()

# ───────────────────────── 1. 태양광 시간별 데이터 ─────────────────────────
df = pd.read_csv(D + 'solar_hourly_sido_2020_2024.csv'); df.columns = [c.strip() for c in df.columns]
df['t'] = pd.to_datetime(df['발전일자'])
n_raw = len(df)
df = df.drop_duplicates(['시도명', 't']).sort_values(['시도명', 't']).reset_index(drop=True)   # 중복 66,976행 제거
df = df.rename(columns={'설비용량(MW)': 'cap', '발전량(MWh)': 'gen', '대기권밖일사량계산값': 'extra',
                        '적운량(10분위)': 'cloud', '강우량(mm)': 'rain', '일조(hr)': 'sun', '일사량': 'ghi',
                        '기온': 'temp', '습도': 'hum', '풍속': 'wind', '적설량(mm)': 'snow'})
df['rain'] = df.rain.fillna(0); df['snow'] = df.snow.fillna(0)
night = (df.extra == 0)
df.loc[night, ['ghi', 'sun']] = df.loc[night, ['ghi', 'sun']].fillna(0)
df['cf'] = df.gen / df.cap
h, d = df.t.dt.hour, df.t.dt.dayofyear
df['hour_sin'], df['hour_cos'] = np.sin(2*np.pi*h/24), np.cos(2*np.pi*h/24)
df['doy_sin'], df['doy_cos'] = np.sin(2*np.pi*d/366), np.cos(2*np.pi*d/366)
df['region'] = df['시도명'].astype('category').cat.codes
key = df[['시도명', 't', 'cf']]
for L in (24, 168):                                          # day-ahead에서 쓸 수 있는 과거값만 (24h 이상)
    k = key.copy(); k['t'] = k.t + pd.Timedelta(hours=L)
    df = df.merge(k.rename(columns={'cf': f'lag{L}'}), on=['시도명', 't'], how='left')
df['day'] = (df.extra > 0) | (df.ghi.fillna(0) > 0)          # 평가·학습 대상: 해가 있는 시간
yr = df.t.dt.year
TR, VA, TE = yr <= 2022, yr == 2023, yr == 2024
log('solar rows', n_raw, '->', len(df))

TIME = ['hour_sin', 'hour_cos', 'doy_sin', 'doy_cos', 'region']
ASTRO = ['extra']
WX = ['temp', 'hum', 'wind', 'cloud', 'rain', 'snow']     # 단기예보에 있는 항목
LAG = ['lag24', 'lag168']
OBS = ['ghi', 'sun']                                       # 예보 항목이 아닌 실측 일사·일조
MAIN_F = TIME + ASTRO + WX + LAG

def fit(cols, target='cf', alpha=None, seed=0):
    tr = TR & df.day & df[target].notna(); va = VA & df.day & df[target].notna()
    p = dict(n_estimators=3000, learning_rate=0.05, num_leaves=63, min_child_samples=50, subsample=0.8,
             subsample_freq=1, colsample_bytree=0.8, random_state=seed, verbose=-1)
    if alpha is not None: p.update(objective='quantile', alpha=alpha)
    m = lgb.LGBMRegressor(**p).fit(df.loc[tr, cols], df.loc[tr, target], eval_set=[(df.loc[va, cols], df.loc[va, target])],
                                   callbacks=[lgb.early_stopping(100, verbose=False)], categorical_feature=['region'])
    return m

def pred(m, cols): return pd.Series(m.predict(df[cols]), index=df.index)
EV = TE & df.day & df.cf.notna() & df.lag24.notna()
def metr(p, mask=EV):
    e = (p - df.cf)[mask]
    return dict(nMAE=round(float(e.abs().mean()*100), 2), nRMSE=round(float(np.sqrt((e**2).mean())*100), 2),
                bias=round(float(e.mean()*100), 2))
def skill(m): return round(1 - m['nRMSE'] / R['A']['Persistence']['nRMSE'], 3)

# 실험 A — 모델별 성능
R['A'] = {}
R['A']['Persistence'] = metr(df.lag24.fillna(0))
X = df[MAIN_F].fillna(df.loc[TR, MAIN_F].median()); trm = TR & df.day & df.cf.notna()
lr = LinearRegression().fit(X[trm], df.cf[trm])
R['A']['선형회귀'] = metr(pd.Series(lr.predict(X), index=df.index).clip(0, 1))
seeds = []
for s in (0, 1, 2):
    m = fit(MAIN_F, seed=s); p = pred(m, MAIN_F).clip(0, 1); seeds.append(metr(p))
    if s == 0: main_model, df['p_main'] = m, p
    log('seed', s, seeds[-1], 'trees', m.best_iteration_)
R['A']['LightGBM'] = {k: round(float(np.mean([x[k] for x in seeds])), 2) for k in seeds[0]}
R['A']['LightGBM']['nRMSE_std'] = round(float(np.std([x['nRMSE'] for x in seeds])), 3)
for k in R['A']: R['A'][k]['Skill'] = skill(R['A'][k])
log('A', R['A'])

# 실험 B — 기상 정보 수준별 (B1이 주 모델과 같음)
R['B'] = {}
m0 = fit(TIME + ASTRO + LAG); R['B']['B0 기상 정보 없음'] = metr(pred(m0, TIME + ASTRO + LAG).clip(0, 1))
R['B']['B1 예보 항목(기온·습도·풍속·운량·강수)'] = {k: v for k, v in seeds[0].items()}
m2 = fit(MAIN_F + OBS); df['p_obs'] = pred(m2, MAIN_F + OBS).clip(0, 1); R['B']['B2 + 실측 일사량·일조'] = metr(df.p_obs)
for k in R['B']: R['B'][k]['Skill'] = skill(R['B'][k])
log('B', R['B'])

# 실험 C — 피처 그룹 누적 추가
R['C'] = {}
steps = [('시간·지역', TIME), ('+ 천문(대기권밖 일사량)', TIME + ASTRO), ('+ 기상 예보 항목', TIME + ASTRO + WX), ('+ 과거 발전량(lag)', MAIN_F)]
for name, cols in steps:
    if cols == MAIN_F: R['C'][name] = dict(seeds[0])
    else: R['C'][name] = metr(pred(fit(cols), cols).clip(0, 1))
    R['C'][name]['Skill'] = skill(R['C'][name])
log('C', R['C'])

# 실험 D — 이용률 정규화 효과 (lag 없이 동일 조건)
NOLAG = TIME + ASTRO + WX
mr = fit(NOLAG, target='gen'); pr = (pred(mr, NOLAG).clip(0) / df.cap)
mc = R['C']['+ 기상 예보 항목']
R['D'] = {'원시 발전량(MWh) 학습': metr(pr), '이용률(CF) 학습': {k: mc[k] for k in ('nMAE', 'nRMSE', 'bias')}}
R['D']['cap_growth'] = {r: [round(float(g[g.t.dt.year == y].cap.max())) for y in range(2020, 2025)] for r, g in df.groupby('시도명')}
R['D']['cap_total'] = [round(float(df[(yr == y)].groupby('시도명').cap.max().sum())) for y in range(2020, 2025)]
log('D', R['D']['원시 발전량(MWh) 학습'])

# 확률 예측 — 분위수 회귀 + 분할 conformal 보정(2023 검증셋으로 범위 폭 보정, 목표 80%)
q = {a: pred(fit(MAIN_F, alpha=a), MAIN_F) for a in (0.1, 0.9)}
df['p10'], df['p90'] = q[0.1].clip(0, 1), q[0.9].clip(0, 1)
vm = VA & df.day & df.cf.notna() & df.lag24.notna()
E = np.maximum(df.p10 - df.cf, df.cf - df.p90)[vm]
qhat = float(np.quantile(E, 0.80))
df['p10c'], df['p90c'] = (df.p10 - qhat).clip(0, 1), (df.p90 + qhat).clip(0, 1)
cov = lambda lo, hi: round(float(((df.cf >= lo) & (df.cf <= hi))[EV].mean()), 3)
R['interval'] = dict(raw_coverage=cov(df.p10, df.p90), conformal_qhat=round(qhat, 4), calibrated_coverage=cov(df.p10c, df.p90c),
                     raw_width=round(float((df.p90 - df.p10)[EV].mean()*100), 2), cal_width=round(float((df.p90c - df.p10c)[EV].mean()*100), 2))
log('interval', R['interval'])

# ── 보완 실험(GPT 조사 반영, handoff/gpt_research.md) — 실패해도 기존 결과는 저장되도록 감싼다 ──
# ① 발행 시각 기준 평가: 전날 14시에 예측한다고 가정 → 관측 기상·lag24를 빼고 lag48·lag168·달력·대기권 밖 일사량만 사용
# ② 같은 입력으로 80% 예측 범위: 2023 상반기로 조기 종료, 하반기로 보정(보정 표본과 모델 선택 표본 분리)
try:
    l48 = key.copy(); l48['t'] = l48.t + pd.Timedelta(hours=48)
    df = df.merge(l48.rename(columns={'cf': 'lag48'}), on=['시도명', 't'], how='left')
    ISSUE = TIME + ASTRO + ['lag48', 'lag168']
    s_ok = (df.extra > 0) & df.cf.notna() & (df.cap > 0)
    issue_ev = TE & s_ok & df.lag48.notna()
    def fit_issue(alpha=None):
        tr_, st_ = TR & s_ok, VA & (df.t.dt.month <= 6) & s_ok
        p_ = dict(n_estimators=3000, learning_rate=0.05, num_leaves=63, min_child_samples=50, subsample=0.8,
                  subsample_freq=1, colsample_bytree=0.8, random_state=0, verbose=-1)
        if alpha is not None: p_.update(objective='quantile', alpha=alpha)
        return lgb.LGBMRegressor(**p_).fit(df.loc[tr_, ISSUE], df.loc[tr_, 'cf'], eval_set=[(df.loc[st_, ISSUE], df.loc[st_, 'cf'])],
                                           categorical_feature=['region'], callbacks=[lgb.early_stopping(100, verbose=False)])
    df['p_issue14'] = pred(fit_issue(), ISSUE).clip(0, 1)
    R['solar_issue_14'] = dict(
        issue='목표일 전날 14:00 발행 가정(시각은 KST로 가정). 관측 기상·lag24 미사용', features=ISSUE,
        test_rows=int(issue_ev.sum()), test_dates=int(df.loc[issue_ev, 't'].dt.normalize().nunique()),
        lag48_baseline=metr(df.lag48, issue_ev), lightgbm=metr(df.p_issue14, issue_ev),
        observed_weather_reference=metr(df.p_main, issue_ev))
    for k_ in ('lightgbm', 'observed_weather_reference'):
        R['solar_issue_14'][k_]['Skill_vs_lag48'] = round(1 - R['solar_issue_14'][k_]['nRMSE'] / R['solar_issue_14']['lag48_baseline']['nRMSE'], 3)
    log('solar_issue_14', R['solar_issue_14'])

    al = 0.20
    q10, q90 = pred(fit_issue(0.10), ISSUE).clip(0, 1), pred(fit_issue(0.90), ISSUE).clip(0, 1)
    lo, hi = np.minimum(q10, q90), np.maximum(q10, q90)              # 분위수 교차 정리
    cal = VA & (df.t.dt.month >= 7) & s_ok & df.lag48.notna()
    sc = np.maximum(lo - df.cf, df.cf - hi)[cal].to_numpy()
    rk = int(np.ceil((len(sc) + 1) * (1 - al)))
    qh = max(0.0, float(np.partition(sc, rk - 1)[rk - 1]))
    loc_, hic = (lo - qh).clip(0, 1), (hi + qh).clip(0, 1)
    def imet(lw, up, m):
        y = df.cf[m]; lw, up = lw[m], up[m]; w = up - lw
        pen = (2 / al) * ((lw - y).clip(lower=0) + (y - up).clip(lower=0))
        return dict(n=int(len(y)), coverage_pct=round(float(100 * ((y >= lw) & (y <= up)).mean()), 2),
                    mean_width_pp=round(float(100 * w.mean()), 2), interval_score_pp=round(float(100 * (w + pen).mean()), 2))
    R['solar_interval_issue_14'] = dict(target_coverage_pct=80, early_stop='2023-01~06', calibration='2023-07~12', n_calibration=int(len(sc)),
        qhat_cf=round(qh, 4), raw_crossings_test=int(((q10 > q90) & issue_ev).sum()),
        raw=imet(lo, hi, issue_ev), calibrated=imet(loc_, hic, issue_ev),
        by_month={int(mo): imet(loc_, hic, issue_ev & (df.t.dt.month == mo)) for mo in sorted(df.loc[issue_ev, 't'].dt.month.unique())})
    log('solar_interval_issue_14', R['solar_interval_issue_14']['calibrated'])
except Exception as e:
    R.setdefault('errors', {})['solar_issue_14'] = repr(e); log('solar_issue_14 실패', repr(e))

# 지역별·월별 성능
reg = []
for r, g in df[EV].groupby('시도명'):
    em, ep = g.p_main - g.cf, g.lag24 - g.cf
    reg.append(dict(region=r, cap2024=round(float(g.cap.max())), nRMSE=round(float(np.sqrt((em**2).mean())*100), 2),
                    pers=round(float(np.sqrt((ep**2).mean())*100), 2)))
R['region'] = sorted(reg, key=lambda x: -x['cap2024'])
mon = df[EV].assign(e=lambda x: x.p_main - x.cf).groupby(df.t.dt.month).e.apply(lambda e: round(float(np.sqrt((e**2).mean())*100), 2))
R['monthly_nRMSE'] = mon.to_dict()
imp = pd.Series(m2.booster_.feature_importance('gain'), index=MAIN_F + OBS); R['importance_B2'] = (imp/imp.sum()*100).round(1).sort_values(ascending=False).to_dict()
imp = pd.Series(main_model.booster_.feature_importance('gain'), index=MAIN_F); R['importance_main'] = (imp/imp.sum()*100).round(1).sort_values(ascending=False).to_dict()

# 데이터 품질 — 야간 발전 비중(연도별), 저녁 시각 불일치
R['night_share'] = {r: {int(y): round(float(g[(g.t.dt.year == y) & (g.extra == 0)].gen.sum() / g[g.t.dt.year == y].gen.sum()*100), 1)
                        for y in range(2020, 2025)} for r, g in df.groupby('시도명')}
R['night_share_total'] = {int(y): round(float(df[(yr == y) & (df.extra == 0)].gen.sum() / df[yr == y].gen.sum()*100), 1) for y in range(2020, 2025)}

# 공식 하루 전 예측(2024-12-01 14시 발표)과 같은 날 비교
kf = pd.read_csv(D + 'kpx_solar_forecast_20241202.csv')
kf['t'] = pd.to_datetime(kf['예측일자'] + ' ' + kf['예측시각'])
kf['cf_kpx'] = kf['계량 태양광 발전량 예측값(MWh)'] / kf['계량 태양광 설비용량(MW)']
cm = kf.merge(df[['시도명', 't', 'cf', 'p_main', 'lag24', 'cap', 'gen', 'day']], on=['시도명', 't'])
cm = cm[cm.day]
R['kpx_day'] = {n: dict(nMAE=round(float((cm[c]-cm.cf).abs().mean()*100), 2), nRMSE=round(float(np.sqrt(((cm[c]-cm.cf)**2).mean())*100), 2))
                for n, c in [('공식 하루 전 예측', 'cf_kpx'), ('우리 모델(관측 기상 입력)', 'p_main'), ('Persistence', 'lag24')]}
R['kpx_day']['n'] = int(len(cm))
cap_k = kf.drop_duplicates('시도명')[['계량 태양광 설비용량(MW)', '소비자발전 태양광 설비용량 추정값(MW)', '전력구매계약 태양광 설비용량 추정값(MW)', '전체 태양광 설비용량(MW)']].sum()
R['metered'] = dict(metered=round(float(cap_k.iloc[0])), btm=round(float(cap_k.iloc[1])), ppa=round(float(cap_k.iloc[2])), total=round(float(cap_k.iloc[3])),
                    share=round(float(cap_k.iloc[0]/cap_k.iloc[3]*100), 1))
log('kpx', R['kpx_day'])

# ───────────────────────── 2. 이상탐지 — 중부발전 발전소별 일별 ─────────────────────────
k = pd.read_csv(D + 'komipo_plants_daily_2023_2026.csv'); k.columns = [c.strip() for c in k.columns]
k['d'] = pd.to_datetime(k['연월일'])
bad = (k.d >= '2025-01-01') & (k.d <= '2025-06-30')
k.loc[bad, '발전량'] = k.loc[bad, '발전량'] / 1000                       # 2025.1~6월 단위 1000배 오류 보정
k.loc[k['발전설비'] == '인천연료전지', '설비용량'] = 31680                 # 2026.3 이전 설비용량 절반 표기 보정
k['설비용량'] = k.groupby('발전설비')['설비용량'].transform('max')         # 0 kW 표기 등 보정
k = k[~k['발전설비'].str.contains('ESS')].drop_duplicates(['연월일', '발전설비'])
k['type'] = np.select([k['발전설비'].str.contains('태양'), k['발전설비'].str.contains('풍력'), k['발전설비'].str.contains('연료'),
                       k['발전설비'].str.contains('소수력')], ['태양광', '풍력', '연료전지', '소수력'], '기타')
k['cf'] = k['발전량'] / (k['설비용량'] * 24)
R['komipo_fix'] = dict(unit_fixed_rows=int(bad.sum()), cf_over_1_after=int((k.cf > 1.05).sum()),
                       plants=k.groupby('type')['발전설비'].nunique().to_dict(), cf_median=k.groupby('type').cf.median().round(3).to_dict())

# (a) 연료전지: 기저 전원처럼 출력이 일정 → 과거 28일 중앙값 대비 이탈 탐지 (3σ, MAD 기반)
fc_res = []
for name, g in k[k.type == '연료전지'].sort_values('d').groupby('발전설비'):
    g = g.set_index('d')
    base = g.cf.shift(1).rolling(28, min_periods=14).median()
    mad = (g.cf - base).abs().shift(1).rolling(90, min_periods=30).median() * 1.4826
    z = (g.cf - base) / mad.replace(0, np.nan)
    drop = base - g.cf
    g = g.assign(base=base, z=z, alert=(z < -3) & (drop >= 0.15))   # 통계적으로 이탈(3σ) + 실무적으로 의미 있는 하락(설비용량의 15%p 이상)
    fc_res.append(g.reset_index())
fcd = pd.concat(fc_res)
R['fuelcell'] = {n: dict(days=int(len(g)), alerts=int(g.alert.sum()), alert_rate=round(float(g.alert.mean()*100), 1),
                         cf_median=round(float(g.cf.median()), 3), drops=int(g.alert.sum()),
                         events=int((g.alert & ~g.alert.shift(1, fill_value=False)).sum()))
                 for n, g in fcd.groupby('발전설비')}
# (a-2) 연료전지 지속 저하(CUSUM, GPT 조사 반영): 처음 90일을 고정 기준선으로 두고 하락을 누적 → 28일 기준선이 놓치는 장기 저하 후보
try:
    R['fuelcell_cusum'] = dict(rule='처음 90달력일(유효 60일 이상) 중앙값·MAD 고정, 하방 CUSUM k=0.5, h=4, 척도 하한 0.02. 결측일은 누적을 끊음',
                               plants={})
    for name, g in fcd.groupby('발전설비'):
        dd = g.sort_values('d').set_index('d')[['cf', 'alert', 'z']].asfreq('D')
        cf_ = dd.cf.where(dd.cf.between(0, 1.05)); bl, mon_ = cf_.iloc[:90].dropna(), cf_.iloc[90:]
        if len(bl) < 60 or not mon_.notna().any():
            R['fuelcell_cusum']['plants'][name] = dict(judgeable=False, baseline_obs=int(len(bl))); continue
        c0 = float(bl.median()); scl = max(1.4826 * float((bl - c0).abs().median()), 0.02)
        sc_, vals = 0.0, []
        for v in mon_:
            if pd.isna(v): sc_ = 0.0; vals.append(np.nan); continue
            sc_ = max(0.0, sc_ + (c0 - v) / scl - 0.5); vals.append(sc_)
        slow = pd.Series(vals, index=mon_.index).ge(4.0)
        acute = dd.loc[mon_.index, 'alert'].eq(True)
        st = slow & ~slow.shift(1, fill_value=False)
        R['fuelcell_cusum']['plants'][name] = dict(judgeable=True, baseline_end=str(cf_.index[89].date()), baseline_cf=round(c0, 3),
            scale_cf=round(scl, 4), monitored_days=int(mon_.notna().sum()), missing_days=int(mon_.isna().sum()),
            first_alert_date=(str(slow.idxmax().date()) if slow.any() else None),   # 기준선 대비 지속 저하가 처음 임계값을 넘은 날
            cusum_alert_days=int(slow.sum()), cusum_events=int(st.sum()), both_alert_days=int((slow & acute).sum()),
            first_starts=[str(x.date()) for x in st.index[st]][:5])
    log('fuelcell_cusum', R['fuelcell_cusum']['plants'])
except Exception as e:
    R.setdefault('errors', {})['fuelcell_cusum'] = repr(e); log('fuelcell_cusum 실패', repr(e))
# (b) 태양광: 같은 날 다른 태양광 발전소 대비 비율 → 날씨 영향 제거 후 저하 탐지
sol = k[k.type == '태양광'].copy()
def area(n):
    for key_, a in [('제주', '제주'), ('인천', '인천'), ('서울', '서울'), ('세종', '세종'), ('여수', '전남'), ('보성', '전남'), ('예천', '경북'), ('괴산', '충북')]:
        if key_ in n: return a
    return '충남'                                                      # 보령·신보령·서천·신서천·태안
sol['area'] = sol['발전설비'].map(area)
na = sol.groupby('area')['발전설비'].nunique()
sol['grp'] = sol.area.where(sol.area.map(na) >= 3, '전국')
sol['peer'] = sol.groupby(['d', 'grp']).cf.transform('median')         # 같은 날·같은 지역 발전소 중앙값
sol['ratio'] = sol.cf / sol.peer
sol = sol[sol.peer > 0.05]
sol['base'] = sol.groupby('발전설비').ratio.transform(lambda x: x.shift(1).rolling(60, min_periods=20).median())
sol['alert'] = sol.ratio < 0.5 * sol.base
sol['event'] = sol.alert & ~sol.groupby('발전설비').alert.shift(1, fill_value=False)
R['solar_peer'] = dict(events=int(sol.event.sum()), groups=sol.groupby('grp')['발전설비'].nunique().to_dict(), plants=int(sol['발전설비'].nunique()), plant_days=int(len(sol)), alerts=int(sol.alert.sum()),
                       top=sol.groupby('발전설비').alert.sum().sort_values(ascending=False).head(5).astype(int).to_dict())
log('anomaly', R['fuelcell'], R['solar_peer'])

# ───────────────────────── 3. 수요와 화력 — '추종' 근거 ─────────────────────────
dm = pd.read_csv(D + 'demand_hourly_2017_2021.csv'); dm['d'] = pd.to_datetime(dm['거래일'])
dm['demand_GWh'] = dm.iloc[:, 1:25].sum(axis=1) / 1000
fu = pd.read_csv(D + 'fuel_daily_region_2018_2022.csv'); fu.columns = [c.strip() for c in fu.columns]
fu['d'] = pd.to_datetime(fu['거래일자'])
fn = fu.pivot_table(index='d', columns='연료원', values='발전량(MWh)', aggfunc='sum') / 1000
j = fn.join(dm.set_index('d')['demand_GWh'], how='inner')
R['follow'] = dict(period=f'{j.index.min().date()}~{j.index.max().date()}', days=int(len(j)),
                   corr={c: round(float(j[c].corr(j.demand_GWh)), 3) for c in ('LNG', '석탄', '유류')},
                   cv={c: round(float(j[c].std()/j[c].mean()), 3) for c in ('LNG', '석탄', 'demand_GWh')},
                   mean_GWh={c: round(float(j[c].mean()), 1) for c in ('LNG', '석탄', '유류', 'demand_GWh')})
# 계절별 하루 수요 곡선
dmh = dm.melt(id_vars=['거래일', 'd'], value_vars=[f'{i}시' for i in range(1, 25)], var_name='h', value_name='MW')
dmh['h'] = dmh.h.str.replace('시', '').astype(int)
dmh['season'] = dmh.d.dt.month.map({12: '겨울', 1: '겨울', 2: '겨울', 6: '여름', 7: '여름', 8: '여름', 3: '봄', 4: '봄', 5: '봄', 9: '가을', 10: '가을', 11: '가을'})
prof = dmh[dmh.d.dt.year == 2021].groupby(['season', 'h']).MW.mean().unstack(0) / 1000
R['demand_profile_2021'] = prof.round(1).to_dict()
th = pd.read_csv(D + 'thermal_units_daily_2022_2023.csv'); th.columns = [c.strip() for c in th.columns]
th['cf'] = th['총발전량'] / (th['용량'] * 1000 * 24)          # 총발전량 kWh, 용량 MW
R['taean'] = dict(units=int(th['호기'].nunique()), cf_mean=round(float(th[th.cf <= 1.05].cf.mean()), 3),
                  minmax_ratio=round(float((th['최소 발전량']/th['최대 발전량']).median()), 3))
log('follow', R['follow'])

# ───────────────────────── 4. 원자력·수급 ─────────────────────────
nc = pd.read_csv(D + 'nuclear_annual_cf_2014_2025.csv')
R['nuclear'] = dict(fleet_median_cf=nc.groupby('년도')['이용률(퍼센트)'].median().round(1).to_dict(),
                    hanbit5=nc[nc['호기'] == '한빛5호기'].set_index('년도')['이용률(퍼센트)'].to_dict(),
                    low_cf_unit_years=int((nc['이용률(퍼센트)'] < 50).sum()), n=int(len(nc)))
nu = pd.read_csv(D + 'nuclear_units_2025.csv')
op = nu[nu['구분'] == '운영원전'].copy(); op['exp'] = pd.to_datetime(op['설계수명만료일'], errors='coerce')
R['nuclear']['expire_by_2030'] = op[op.exp <= '2030-12-31'][['발전소명', '호기', '설계수명만료일']].values.tolist()
R['nuclear']['operating_units'] = int(len(op))
sp = pd.read_csv(D + 'supply_daily_2025.csv'); sp.columns = [c.strip() for c in sp.columns]
sp = sp.rename(columns={sp.columns[2]: 'supply_cap', sp.columns[3]: 'peak', sp.columns[5]: 'reserve', sp.columns[6]: 'rate'})  # 열 이름 한 칸 밀림 보정
sp['d'] = pd.to_datetime(sp.iloc[:, 0]); sp['wk'] = sp.d.dt.dayofweek >= 5
R['supply2025'] = dict(identity_max_err_MW=float((sp.supply_cap - sp.peak - sp.reserve).abs().max()),
                       peak_max=float(sp.peak.max()), peak_day=str(sp.loc[sp.peak.idxmax(), 'd'].date()),
                       rate_min=float(sp.rate.min()), rate_min_day=str(sp.loc[sp.rate.idxmin(), 'd'].date()),
                       rate_weekday=round(float(sp[~sp.wk].rate.mean()), 1), rate_weekend=round(float(sp[sp.wk].rate.mean()), 1),
                       monthly_peak=(sp.groupby(sp.d.dt.month).peak.max()/1000).round(1).to_dict())
log('nuclear/supply done')
json.dump(R, open('results/results.json', 'w'), ensure_ascii=False, indent=1, default=str)

# ───────────────────────── 5. 그림 ─────────────────────────
# F1 모델 비교
fig, ax = plt.subplots(figsize=(7, 3.6))
names = ['Persistence\n(어제 같은 시각)', '선형회귀', 'LightGBM']
vals = [R['A']['Persistence']['nRMSE'], R['A']['선형회귀']['nRMSE'], R['A']['LightGBM']['nRMSE']]
b = ax.barh(names[::-1], vals[::-1], color=[MAIN, MUTED, MUTED])
for bb, v in zip(b, vals[::-1]): ax.text(v + .3, bb.get_y() + bb.get_height()/2, f'{v:.1f}%', va='center', color=INK)
ax.set_xlabel('nRMSE (설비용량 대비 오차, %) — 낮을수록 좋음'); ax.set_xlim(0, max(vals)*1.2)
save('f1_models.png')

# F2 기상 정보 수준(B)
fig, ax = plt.subplots(figsize=(7, 3.6))
bn = ['기상 정보 없음', '예보 항목\n(기온·습도·풍속·운량·강수)', '+ 실측 일사량']
bv = [R['B'][k]['nRMSE'] for k in R['B']]
ax.bar(bn, bv, color=[MUTED, MAIN, ACC], width=.6)
for i, v in enumerate(bv): ax.text(i, v + .2, f'{v:.1f}%', ha='center', color=INK)
ax.axhline(R['A']['Persistence']['nRMSE'], color=BAD, ls='--', lw=1); ax.text(2.35, R['A']['Persistence']['nRMSE']+.3, '어제 값', color=BAD, ha='right', fontsize=9)
ax.set_ylabel('nRMSE (%)')
save('f2_weather_info.png')

# F3 맑은 날 / 크게 틀린 날 (전남, 보정된 P10~P90)
p = df[TE & (df['시도명'] == '전남')].copy(); p['dd'] = p.t.dt.date
de = p[p.day].assign(err=lambda x: (x.p_main - x.cf).abs()).groupby('dd').err.mean()
cl = p[(p.t.dt.hour.between(10, 14))].groupby('dd').cloud.mean()
good = de[cl[cl <= 1].index.intersection(de.index)].idxmin(); worst = de.idxmax()
fig, axs = plt.subplots(1, 2, figsize=(12, 4.2), sharey=True)
for a, dd, tt in zip(axs, [good, worst], ['맑은 날 — 잘 맞음', '크게 틀린 날']):
    s = p[p.dd == dd].copy(); x = s.t.dt.hour
    s.loc[~s.day, ['p_main', 'p10c', 'p90c']] = 0                     # 모델은 해가 있는 시간만 예측
    a.fill_between(x, s.p10c, s.p90c, color=MAIN, alpha=.18, lw=0, label='P10~P90 (보정)')
    a.plot(x, s.cf, '-o', color=INK, ms=3, label='실제'); a.plot(x, s.p_main, '-', color=MAIN, lw=2.2, label='AI 예측')
    a.plot(x, s.lag24, '--', color=ACC, label='어제 같은 시각')
    a.set_title(f'전남 {dd} · {tt}', loc='left'); a.set_xlabel('시각'); a.grid(alpha=.25)
axs[0].set_ylabel('이용률 (발전량 ÷ 설비용량)'); axs[0].legend(loc='upper left', fontsize=9, frameon=False)
R['fig_days'] = dict(good=str(good), worst=str(worst))
save('f3_days.png')

# F4 설비 증가와 정규화 효과
fig, axs = plt.subplots(1, 2, figsize=(11, 3.8))
axs[0].bar(range(2020, 2025), [v/1000 for v in R['D']['cap_total']], color=MAIN, width=.6)
for x_, v in zip(range(2020, 2025), R['D']['cap_total']): axs[0].text(x_, v/1000 + .1, f'{v/1000:.1f}', ha='center')
axs[0].set_title('데이터 속 계량 태양광 설비용량 (GW)', loc='left')
lab = ['원시 발전량으로 학습', '이용률로 학습']
bias = [R['D']['원시 발전량(MWh) 학습']['bias'], R['D']['이용률(CF) 학습']['bias']]
axs[1].bar(lab, bias, color=[BAD, MAIN], width=.5); axs[1].axhline(0, color=INK, lw=.8)
for i, v in enumerate(bias): axs[1].text(i, v + (-.6 if v < 0 else .2), f'{v:+.1f}%p', ha='center', color=INK)
axs[1].set_title('2024년 예측 치우침 (설비용량 대비)', loc='left')
save('f4_normalize.png')

# F5 지역별
rg = pd.DataFrame(R['region'])
fig, ax = plt.subplots(figsize=(8, 4.2)); x = np.arange(len(rg))
ax.bar(x - .2, rg.pers, .4, color=MUTED, label='어제 값'); ax.bar(x + .2, rg.nRMSE, .4, color=MAIN, label='AI 예측')
ax.set_xticks(x, rg.region); ax.set_ylabel('nRMSE (%)'); ax.legend(frameon=False); ax.set_title('지역별 오차 (설비용량 큰 순)', loc='left')
save('f5_region.png')

# F6 야간 발전 비중
ns = pd.DataFrame(R['night_share']).T
fig, ax = plt.subplots(figsize=(7, 3.8))
for r_ in ['전남', '전북', '충북', '강원', '인천']: ax.plot(ns.columns, ns.loc[r_], '-o', ms=3, label=r_, lw=1.4)
ax.plot(list(R['night_share_total'].keys()), list(R['night_share_total'].values()), '-o', color=INK, lw=3, label='전국')
ax.set_ylabel('해가 없는 시간의 발전량 비중 (%)'); ax.legend(frameon=False, ncol=3, fontsize=9); ax.set_xticks(range(2020, 2025))
save('f6_night.png')

# F7 공식 예측과 같은 날 비교 (전국 합계)
agg = cm.groupby('t').apply(lambda g: pd.Series({'실제': g.gen.sum(), '공식 하루 전 예측': (g.cf_kpx*g.cap).sum(), '우리 모델': (g.p_main*g.cap).sum()}))
fig, ax = plt.subplots(figsize=(7, 3.8))
ax.plot(agg.index.hour, agg['실제'], '-o', color=INK, ms=3, label='실제'); ax.plot(agg.index.hour, agg['공식 하루 전 예측'], '--', color=ACC, lw=2, label='공식 하루 전 예측')
ax.plot(agg.index.hour, agg['우리 모델'], '-', color=MAIN, lw=2, label='우리 모델 (관측 기상 입력)')
ax.set_ylabel('MWh (17개 시도 합계)'); ax.set_xlabel('시각'); ax.legend(frameon=False); ax.set_title('2024-12-02 하루', loc='left')
save('f7_kpx_day.png')

# F8 연료전지 이상탐지 예시
nm = '세종연료전지'
g = fcd[fcd['발전설비'] == nm]
fig, ax = plt.subplots(figsize=(9, 3.6))
ax.plot(g.d, g.cf, color=MUTED, lw=1, label='일별 이용률'); ax.plot(g.d, g.base, color=MAIN, lw=2, label='정상 패턴(과거 28일 중앙값)')
a_ = g[g.alert]; ax.scatter(a_.d, a_.cf, color=BAD, s=14, zorder=3, label=f'이상 알림 {len(a_)}건')
ax.set_title(f'{nm} — 정상 패턴보다 15%p 이상 떨어진 날', loc='left'); ax.set_ylabel('이용률'); ax.legend(frameon=False, fontsize=9, loc='lower left')
R['fig_fuelcell'] = nm
save('f8_fuelcell.png')

# F9 수요와 화력
jw = j.rolling(7).mean()
fig, ax = plt.subplots(figsize=(9, 3.6))
ax.plot(jw.index, jw.demand_GWh, color=INK, lw=1.5, label='전력수요')
ax.plot(jw.index, jw.LNG, color=MAIN, lw=1.5, label='LNG 발전'); ax.plot(jw.index, jw['석탄'], color=ACC, lw=1.5, label='석탄 발전')
ax.set_ylabel('GWh/일 (7일 평균)'); ax.legend(frameon=False, ncol=3)
save('f9_follow.png')

# F10 원전 이용률
fig, ax = plt.subplots(figsize=(8, 3.6))
fm_ = pd.Series(R['nuclear']['fleet_median_cf']); hb = pd.Series(R['nuclear']['hanbit5'])
ax.plot(fm_.index, fm_.values, '-o', color=MUTED, ms=3, label='전체 호기 중앙값'); ax.plot(hb.index, hb.values, '-o', color=BAD, lw=2, ms=4, label='한빛 5호기')
ax.set_ylabel('연간 이용률 (%)'); ax.set_ylim(0, 110); ax.legend(frameon=False)
save('f10_nuclear.png')
json.dump(R, open('results/results.json', 'w'), ensure_ascii=False, indent=1, default=str)
log('done')
