"""공공데이터포털 추가 자료 3차(GPT 조사 추천, 12종) 분석 — 총 50종 맞춤
입력: data/public/<포털번호>.csv|zip  (python fetch_data.py --public)
출력: results/results.json 의 'public3' 키, figures/f24~f26
실행: python analyze_public2.py 다음에 python analyze_public3.py (수십 초)
"""
import io, json, os, zipfile
import numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

for FONT in ['/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
             'C:/Windows/Fonts/malgun.ttf', '/System/Library/Fonts/AppleSDGothicNeo.ttc']:
    if os.path.exists(FONT):
        fm.fontManager.addfont(FONT); plt.rcParams['font.family'] = fm.FontProperties(fname=FONT).get_name(); break
plt.rcParams.update({'axes.unicode_minus': False, 'axes.spines.top': False, 'axes.spines.right': False, 'figure.dpi': 150})
INK, MUTED, MAIN, ACC, BAD = '#1d2b36', '#8a96a0', '#0f6e6a', '#e8a33d', '#c0392b'
P, F, RJ = 'data/public/', 'figures/', 'results/results.json'
R = json.load(open(RJ, encoding='utf-8')); OUT, SRC = {}, {}
def save(name): plt.tight_layout(); plt.savefig(F + name, dpi=200); plt.close()
def text(b):
    for e in ('utf-8-sig', 'cp949'):
        try: return b.decode(e)
        except UnicodeDecodeError: pass
    return b.decode('utf-8', 'replace')
def csv(pk):
    d = pd.read_csv(io.StringIO(text(open(f'{P}{pk}.csv', 'rb').read())), skipinitialspace=True); d.columns = [c.strip() for c in d.columns]; return d
def zcsvs(pk):
    z = zipfile.ZipFile(f'{P}{pk}.zip')
    for n in z.namelist():
        if n.lower().endswith('.csv'):
            d = pd.read_csv(io.StringIO(text(z.read(n)))); d.columns = [c.strip() for c in d.columns]; yield n, d
def num(s): return pd.to_numeric(s.astype(str).str.replace(',', '').str.strip(), errors='coerce')
def rmse(e): return float(np.sqrt(np.nanmean(np.square(e))))
def step(name, fn):
    try: OUT[name] = fn(); print('[ok]', name)
    except Exception as e: OUT.setdefault('errors', {})[name] = repr(e); print('[실패]', name, repr(e))
def peer_low(df, thr):
    """열=설비, 행=날짜. 같은 날 다른 설비 중앙값 대비 비율이 thr 미만인 날 수"""
    med = df.median(axis=1); return {c: int((df[c] / med.replace(0, np.nan) < thr).sum()) for c in df.columns}

# ── ② 서부발전 호기별 일별 열효율 (15106338): 효율이 평소보다 떨어진 날 ──
def wp_daily():
    SRC['15106338'] = '한국서부발전(주)_일별 발전실적 정보'
    d = csv(15106338); d['d'] = pd.to_datetime(d['연월일'], errors='coerce')
    for c in ['설비용량(MW)', '발전량(MWh)', '열효율(퍼센트)', '이용율(퍼센트)']: d[c] = num(d[c])
    d = d[(d['열효율(퍼센트)'] > 5) & (d['이용율(퍼센트)'] > 30)].copy()         # 정상 운전일(이용률 30% 이상)만
    d['key'] = d['발전소명'] + ' ' + d['호기'].astype(str); d = d.sort_values(['key', 'd'])
    g = d.groupby('key')['열효율(퍼센트)']
    d['base'] = g.transform(lambda s: s.shift(1).rolling(28, min_periods=14).median())
    d['mad'] = g.transform(lambda s: (s - s.shift(1).rolling(28, min_periods=14).median()).abs().shift(1).rolling(90, min_periods=30).median() * 1.4826)
    d['alert'] = (d.base - d['열효율(퍼센트)']) > np.maximum(3 * d.mad, 1.0)    # 3σ 이상이면서 1%p 넘게 하락
    by = d.groupby('발전원').agg(units=('key', 'nunique'), eff_median=('열효율(퍼센트)', 'median')).round(1).to_dict(orient='index')
    return dict(period=f"{d.d.min().date()}~{d.d.max().date()}", by_source=by, judged_days=int(d.base.notna().sum()), alert_days=int(d.alert.sum()),
                top_units=d[d.alert].key.value_counts().head(5).to_dict())

# ── ③ 서부발전 풍력 발전기별 시간별 (15106292): 어제 값 예측 오차 ──
def wp_wind():
    SRC['15106292'] = '한국서부발전(주)_풍력 발전 현황'
    d = csv(15106292); d['d'] = pd.to_datetime(d['년월일'], errors='coerce'); hc = [c for c in d.columns if c.endswith('시')]
    out = {}
    for name, g in d.groupby('발전기명'):
        cap = num(g['설비용량(MW)']).max() * 1000                              # kWh/h 기준
        h = g.melt(id_vars=['d'], value_vars=hc, var_name='h', value_name='p'); h['p'] = num(h.p)
        h['t'] = h.d + pd.to_timedelta(h.h.str[:2].astype(int) - 1, unit='h'); s = h.set_index('t').p.sort_index()
        s = s[~s.index.duplicated()].asfreq('h'); cf = (s / cap).where(lambda x: x.between(0, 1.1))
        if cf.notna().sum() < 1000: continue
        out[name] = dict(cap_MW=round(cap / 1000, 1), period=f'{s.index.min().date()}~{s.index.max().date()}', cf_mean=round(float(cf.mean()), 3),
                         persistence_nRMSE=round(rmse((cf - cf.shift(24)).dropna()) * 100, 2))
    return out

# ── ③ 성산풍력 호기별 일평균 풍속 (15076400): 같은 단지 호기끼리 비교 ──
def seongsan():
    SRC['15076400'] = '한국남부발전(주)_성산풍력 일평균 풍속데이터'
    d = csv(15076400); d['d'] = pd.to_datetime(d.iloc[:, 0], errors='coerce'); u = [c for c in d.columns if '호기' in c]
    for c in u: d[c] = num(d[c])
    w = d.set_index('d')[u]; w = w[w.median(axis=1) >= 3]                       # 바람이 약한 날 제외
    ratio = w.div(w.median(axis=1), axis=0)
    low = peer_low(w, 0.8)
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.bar([c.replace('성산', '') for c in u], [low[c] for c in u], color=[BAD if low[c] > np.median(list(low.values())) * 3 else MAIN for c in u])
    ax.set_ylabel('단지 중앙값보다 20% 이상 약한 날'); ax.set_title(f'성산풍력 10기 — 같은 날 다른 호기와 풍속 비교 ({w.index.min():%Y}~{w.index.max():%Y})', loc='left', fontsize=10)
    save('f25_seongsan_peer.png')
    return dict(units=len(u), days=int(len(w)), period=f'{w.index.min().date()}~{w.index.max().date()}', low_days_by_unit=low,
                median_ratio_by_unit=ratio.median().round(3).to_dict(),
                note='풍속계 이상, 후류(앞 터빈 뒤의 약한 바람), 정지를 구분하려면 발전량·정비 기록이 필요하다')

# ── ③ 남동발전 태양광 시간별 + 메타데이터 (15167614): 같은 날 발전소끼리 비교 ──
def kosep_solar():
    SRC['15167614'] = '한국남동발전㈜_시간대별_태양광_실적_및_메타데이터'
    d = csv(15167614); d['d'] = pd.to_datetime(d['발전일'], errors='coerce'); d['tot'] = num(d['총량(KW)'])
    d['key'] = d['발전구분'] + ' ' + d['호기'].astype(str)
    p = d.pivot_table(index='d', columns='key', values='tot', aggfunc='sum')
    rel = p / p.rolling(60, min_periods=20).quantile(0.9)                        # 각 발전소의 최근 60일 상위 10% 대비
    meta = d.drop_duplicates('key').set_index('key')[['지역', '설치각', '향']].astype(str)
    low = {k: int(v) for k, v in peer_low(rel, 0.5).items()}
    return dict(plants=int(p.shape[1]), days=int(p.shape[0]), period=f'{p.index.min().date()}~{p.index.max().date()}', regions=meta['지역'].value_counts().to_dict(),
                peer_low_days_top=dict(sorted(low.items(), key=lambda x: -x[1])[:5]), peer_low_days_total=int(sum(low.values())),
                note='각 발전소 발전량을 자기 최근 60일 상위 10% 값으로 나눈 뒤, 같은 날 다른 발전소 중앙값의 절반 미만인 날을 저하 후보로 셈')

# ── ③ 한수원 수력·양수 월별 (15041895) ──
def hydro_pump():
    SRC['15041895'] = '한국수력원자력(주)_수력양수 발전량 및 이용률'
    d = csv(15041895)
    for c in d.columns[1:]: d[c] = num(d[c])
    return dict(period=f"{d.iloc[0, 0]}~{d.iloc[-1, 0]}", hydro_cf_range=[float(d.iloc[:, 2].min()), float(d.iloc[:, 2].max())],
                pumped_cf_range=[float(d.iloc[:, 4].min()), float(d.iloc[:, 4].max())],
                hydro_GWh_total=round(float(d.iloc[:, 1].sum() / 1e6), 1), pumped_GWh_total=round(float(d.iloc[:, 3].sum() / 1e6), 1))

# ── ②④ 서부발전 대기오염물질 + 발전량 (15099592): 발전량당 NOx ──
def wp_emission():
    SRC['15099592'] = '한국서부발전(주)_대기오염물질 배출현황 및 발전량'
    d = csv(15099592); d['y'] = d['날짜'].astype(str).str[:4].astype(int)
    for c in ['발전량(MWh)', 'SOx', 'NOx', '먼지(TSP)']: d[c] = num(d[c])
    t = d[d['발전소'] == '태안'].groupby('y')[['발전량(MWh)', 'NOx', 'SOx']].sum()
    t = t[(t.NOx > 0) & (t['발전량(MWh)'] > 0)]
    inten = (t.NOx / t['발전량(MWh)'] * 1000).round(3)                          # 원자료 단위 기준 NOx / GWh
    return dict(plants=sorted(d['발전소'].unique().tolist()), period=f"{d['날짜'].min()}~{d['날짜'].max()}",
                taean_nox_per_GWh_by_year={int(k): float(v) for k, v in inten.items()},
                note='배출량 원자료 단위가 표기되지 않아 연도별 상대 추이만 본다')

# ── ④ 남부발전 온실가스 (15074207) ──
def kospo_ghg():
    SRC['15074207'] = '한국남부발전(주)_온실가스 배출량 정보'
    d = csv(15074207); s1 = [c for c in d.columns if 'Scope1' in c]
    tot = {c[:4]: round(float(num(d[c]).sum()), 1) for c in s1}
    return dict(scope1_total_10kt_by_year=tot, sites=int(len(d)))

# ── ② 중부발전 연료 입출고·재고 (15155623): 유연탄 재고 일수 ──
def komipo_fuel():
    SRC['15155623'] = '한국중부발전(주)_발전소별 발전연료 입출고 및 재고 현황'
    d = csv(15155623)
    for c in ['당월재고 수량', '출고수량']: d[c] = num(d[c])
    c = d[d['연료종류'].astype(str).str.contains('유연탄')]
    days = (c['당월재고 수량'] / (c['출고수량'] / 30)).replace([np.inf, -np.inf], np.nan)
    by = c.assign(days=days).groupby('발전소명').days.median().round(1).dropna().to_dict()
    return dict(fuels=d['연료종류'].value_counts().head(8).to_dict(), period=f"{d['연월'].min()}~{d['연월'].max()}", coal_stock_days_median_by_plant=by)

# ── ② 남동발전 온배수 수온 (15144100) ──
def kosep_thermal_water():
    SRC['15144100'] = '한국남동발전㈜_온배수 수온 현황'
    d = csv(15144100); d['in'], d['out'] = num(d.iloc[:, 2]), num(d.iloc[:, 3]); d['m'] = pd.to_datetime(d.iloc[:, 1]).dt.month
    d['dt'] = d.out - d['in']
    return dict(sites=d.iloc[:, 0].unique().tolist(), delta_T_median_by_site=d.groupby(d.iloc[:, 0]).dt.median().round(1).to_dict(),
                intake_temp_by_month=d.groupby('m')['in'].median().round(1).to_dict(),
                note='바닷물 취수 온도가 높은 여름에는 냉각이 덜 돼 화력 효율이 떨어진다 → 계절별 효율 기준선이 필요한 이유')

# ── ②④ SMP 결정 연료원 2025 (15161908): 누가 전기 가격을 정하나 ──
def smp_fuel():
    SRC['15161908'] = '한국전력거래소_육지 및 제주 계통한계가격(SMP) 결정 발전기 연료원'
    out = {}
    for n, d in zcsvs(15161908):
        k = '육지' if '육지' in n else '제주'; s = d.iloc[:, -1].astype(str).str.strip().value_counts(normalize=True) * 100
        out[k] = s.round(1).to_dict()
    land = out.get('육지', {})
    fig, ax = plt.subplots(figsize=(7, 3.4)); ks = list(land)[:6]
    ax.barh(ks[::-1], [land[k] for k in ks][::-1], color=MAIN)
    for i, k in enumerate(ks[::-1]): ax.text(land[k] + .5, i, f'{land[k]:.1f}%', va='center', fontsize=9)
    ax.set_xlabel('2025년 육지 시간 중 비율 (%)'); ax.set_title('전기 도매가격(SMP)을 정한 발전기의 연료', loc='left')
    save('f24_smp_fuel.png')
    return out

# ── ② 2025 시간별 전국 전력수요 (15065266): 수요는 얼마나 예측하기 쉬운가 ──
def demand_2025():
    SRC['15065266'] = '한국전력거래소_시간별 전국 전력수요량'
    d = csv(15065266).dropna(subset=['날짜']); d['d'] = pd.to_datetime(d['날짜'], errors='coerce'); d = d.dropna(subset=['d'])
    hc = [f'{i}시' for i in range(1, 25)]
    h = d.melt(id_vars=['d'], value_vars=hc, var_name='h', value_name='MW'); h['MW'] = num(h.MW)
    h['t'] = h.d + pd.to_timedelta(h.h.str.replace('시', '').astype(int) - 1, unit='h'); s = h.set_index('t').MW.sort_index().asfreq('h')
    peak = s.max(); ramp = s.diff()
    return dict(peak_MW=float(peak), peak_time=str(s.idxmax()), max_hourly_ramp_up_MW=float(ramp.max()), max_hourly_ramp_down_MW=float(ramp.min()),
                persistence24_nRMSE_of_peak=round(rmse((s - s.shift(24)).dropna()) / peak * 100, 2),
                persistence168_nRMSE_of_peak=round(rmse((s - s.shift(168)).dropna()) / peak * 100, 2),
                note='수요는 같은 요일 지난주 값으로도 최대전력 대비 오차가 작다 — 풍력·태양광보다 예측이 쉬운 쪽')

# ── ② 하수처리 혐기성 소화조 (15151942): 바이오가스 생산 이상 후보 ──
def digester():
    SRC['15151942'] = '광주환경공단_1하수관리처_혐기성 소화조 운영 데이터'
    d = csv(15151942); d['d'] = pd.to_datetime(d['기준일자'], errors='coerce')
    for c in ['온도', '메탄함량', '바이오가스생산량', '소화조유입량']: d[c] = num(d[c])
    g = d.groupby('d')[['바이오가스생산량', '온도', '소화조유입량']].agg({'바이오가스생산량': 'sum', '온도': 'mean', '소화조유입량': 'sum'})
    g = g[g['바이오가스생산량'] > 0].asfreq('D')
    base = g['바이오가스생산량'].shift(1).rolling(28, min_periods=14).median(); alert = g['바이오가스생산량'] < 0.6 * base
    ok = g[['바이오가스생산량', '온도']].dropna()
    fig, ax = plt.subplots(figsize=(8, 3.4)); ax.plot(g.index, g['바이오가스생산량'], color=MUTED, lw=.8, label='일 바이오가스 생산량')
    ax.plot(base.index, base, color=MAIN, lw=1.6, label='정상 패턴(28일 중앙값)'); a = g[alert]; ax.scatter(a.index, a['바이오가스생산량'], s=10, color=BAD, label=f'40% 이상 감소 {int(alert.sum())}일')
    ax.set_ylabel('㎥/일'); ax.legend(frameon=False, fontsize=8); ax.set_title('하수처리장 소화조 바이오가스 — 평소와 다른 날', loc='left')
    save('f26_biogas_digester.png')
    return dict(period=f'{g.index.min().date()}~{g.index.max().date()}', days=int(g['바이오가스생산량'].notna().sum()), alert_days=int(alert.sum()),
                corr_temp_biogas=round(float(ok.corr().iloc[0, 1]), 3))

for name, fn in [('wp_daily_eff', wp_daily), ('wp_wind', wp_wind), ('seongsan_wind', seongsan), ('kosep_solar', kosep_solar), ('hydro_pump', hydro_pump),
                 ('wp_emission', wp_emission), ('kospo_ghg', kospo_ghg), ('komipo_fuel', komipo_fuel), ('kosep_cooling_water', kosep_thermal_water),
                 ('smp_fuel_2025', smp_fuel), ('demand_2025', demand_2025), ('biogas_digester', digester)]:
    step(name, fn)
OUT['sources'] = SRC
R['public3'] = OUT
def clean(o):
    if isinstance(o, dict): return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [clean(v) for v in o]
    if isinstance(o, float) and not np.isfinite(o): return None
    if isinstance(o, np.generic): return clean(o.item())
    return o
json.dump(clean(R), open(RJ, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str, allow_nan=False)
print('wrote public3:', [k for k in OUT if k != 'sources'], '| 자료', len(SRC), '종')
