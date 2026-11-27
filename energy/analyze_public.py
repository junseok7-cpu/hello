"""공공데이터포털 추가 자료(16종) 분석 — 발표 파트 ①~④ 보강
입력: data/public/<포털번호>.csv|zip (python fetch_data.py --public 으로 받음), data/ 의 기본 9종 일부
출력: results/results.json 의 'public' 키(기존 키는 그대로), figures/f13~f18
실행: python analyze.py && python analyze_extra.py && python analyze_public.py
"""
import io, json, os, re, zipfile
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
P, D, F, RJ = 'data/public/', 'data/', 'figures/', 'results/results.json'
R = json.load(open(RJ, encoding='utf-8'))
PUB = {}
def save(name): plt.tight_layout(); plt.savefig(F + name, dpi=200); plt.close()
def text(b):
    for e in ('utf-8-sig', 'cp949'):
        try: return b.decode(e)
        except UnicodeDecodeError: pass
def csv(pk):
    df = pd.read_csv(io.StringIO(text(open(f'{P}{pk}.csv', 'rb').read())), skipinitialspace=True)
    df.columns = [c.strip() for c in df.columns]
    return df
def num(s): return pd.to_numeric(s.astype(str).str.replace(',', '').str.strip(), errors='coerce')
def step(name, fn):
    try: PUB[name] = fn(); print('[ok]', name)
    except Exception as e: PUB.setdefault('errors', {})[name] = repr(e); print('[실패]', name, repr(e))
SRC = {}  # 사용한 포털 자료 목록

# ───────── 파트 ① 지열: 국립세종수목원 지열 히트펌프 시간별 운전 기록 (15126707) ─────────
def geothermal():
    SRC['15126707'] = '한국수목원정원관리원_국립세종수목원 지열 이용량'
    z = zipfile.ZipFile(P + '15126707.zip'); rows = []
    for n in z.namelist():
        if not n.endswith('.xlsx'): continue
        x = pd.read_excel(io.BytesIO(z.read(n)), header=None, engine='openpyxl')
        bld = [str(v).strip() for v in x.iloc[6, 1:].dropna().tolist()]   # 첫 열(시간) 제외          # 건물 이름 2개(예: 사계절온실, 방문자센터)
        body = x.iloc[10:].copy()
        body = body[pd.to_datetime(body[0], errors='coerce').notna()]
        for k, b in enumerate(bld[:2]):
            c = 1 + 10 * k                                            # 건물마다 10열: 입수온도, 출수온도, 유량, 순시열량, 누적열량, 순시전력, 누적전력, COP 순시, COP 누적, 생산시간
            sub = pd.DataFrame({'t': pd.to_datetime(body[0]), 'bld': b,
                                'tin': pd.to_numeric(body[c], errors='coerce'), 'tout': pd.to_numeric(body[c + 1], errors='coerce'),
                                'flow': pd.to_numeric(body[c + 2], errors='coerce'), 'heat_kw': pd.to_numeric(body[c + 3], errors='coerce'),
                                'power_kw': pd.to_numeric(body[c + 5], errors='coerce'), 'cop': pd.to_numeric(body[c + 7], errors='coerce')})
            rows.append(sub)
    g = pd.concat(rows).dropna(subset=['heat_kw', 'power_kw']).drop_duplicates(['t', 'bld'])
    run = g[(g.heat_kw > 1) & (g.power_kw > 0.5)].copy()             # 실제 운전 중인 시간만
    run['cop_calc'] = run.heat_kw / run.power_kw
    run = run[run.cop_calc.between(0.5, 10)]                         # 계측 오류 제외
    run['m'] = run.t.dt.month
    d = run.assign(day=run.t.dt.normalize()).groupby(['bld', 'day']).agg(heat=('heat_kw', 'sum'), power=('power_kw', 'sum'), tin=('tin', 'mean')).reset_index()
    d['cop'] = d.heat / d.power
    out = dict(period=f'{g.t.min().date()}~{g.t.max().date()}', hours_total=int(len(g)), hours_running=int(len(run)),
               buildings=sorted(run.bld.unique().tolist()),
               cop_median=round(float(run.cop_calc.median()), 2), cop_p10=round(float(run.cop_calc.quantile(.1)), 2), cop_p90=round(float(run.cop_calc.quantile(.9)), 2),
               cop_by_month=run.groupby('m').cop_calc.median().round(2).to_dict(),
               corr_daily_cop_vs_inlet_temp=round(float(d[['cop', 'tin']].corr().iloc[0, 1]), 3), days=int(len(d)))
    # 이상 후보: 건물별 과거 28일 중앙값 대비 일 COP가 30% 이상 낮은 날 (운전 4시간 이상인 날)
    hrs = run.assign(day=run.t.dt.normalize()).groupby(['bld', 'day']).size().rename('hrs').reset_index()
    d = d.merge(hrs, on=['bld', 'day']); d = d[d.hrs >= 4].sort_values(['bld', 'day'])
    d['base'] = d.groupby('bld').cop.transform(lambda s: s.shift(1).rolling(28, min_periods=10).median())
    d['alert'] = d.cop < 0.7 * d.base
    out['cop_drop_alert_days'] = d.groupby('bld').alert.sum().astype(int).to_dict()
    out['judged_days'] = d.groupby('bld').base.count().astype(int).to_dict()
    fig, axs = plt.subplots(1, 2, figsize=(11, 3.8))
    for b, gg in d.groupby('bld'): axs[0].plot(gg.day, gg.cop.rolling(7, min_periods=3).median(), lw=1.2, label=b)
    axs[0].set_title('일별 COP(생산열량 ÷ 소비전력), 7일 중앙값', loc='left'); axs[0].set_ylabel('COP'); axs[0].legend(frameon=False, fontsize=8)
    axs[1].scatter(d.tin, d.cop, s=4, alpha=.35, color=MAIN); axs[1].set_xlabel('지열측 입수온도 평균 (℃)'); axs[1].set_ylabel('일 COP')
    axs[1].set_title(f"입수온도와 효율 (상관 {out['corr_daily_cop_vs_inlet_temp']:.2f})", loc='left')
    save('f13_geothermal.png')
    return out

# ───────── 파트 ① 수열·지열·바이오 생산량 추이 (15157241), 외부 수열 (15149953), 시간별 수열량 (15123991) ─────────
def heat_sources():
    SRC['15157241'] = '기후에너지환경부_신재생에너지 생산량'; SRC['15149953'] = '한국지역난방공사_연도별 공급자별 외부 수열량'; SRC['15123991'] = '한국지역난방공사_시간대별 수열량 정보'
    pr = csv(15157241); pr['생산량'] = num(pr['생산량']); pr['연도'] = num(pr['연도']).astype(int)
    pr['grp'] = pr['구분'].str.split('-').str[0]
    piv = pr.pivot_table(index='연도', columns='grp', values='생산량', aggfunc='sum')
    keep = [c for c in ['지열', '수열', '바이오', '연료전지', '태양광', '풍력'] if c in piv]
    out = dict(unit='생산량(원자료 단위 표기 없음 — 확인 필요)', production=piv[keep].round(0).astype(int).to_dict(),
               growth_2015_2024={c: round(float(piv[c].iloc[-1] / piv[c].iloc[0]), 2) for c in keep if piv[c].iloc[0] > 0})
    ex = csv(15149953); ex['수열량'] = num(ex['수열량'])
    out['external_heat_latest'] = ex[ex['연도'] == ex['연도'].max()].groupby('종류')['수열량'].sum().sort_values(ascending=False).to_dict()
    out['external_heat_year'] = int(ex['연도'].max())
    hh = csv(15123991); hh['h'] = num(hh['시간']).astype(int); v = num(hh.iloc[:, 4])
    out['sejong_hourly_profile'] = hh.assign(v=v).groupby('h').v.mean().round(1).to_dict()
    out['sejong_period'] = f"{hh['일자'].min()}~{hh['일자'].max()}"
    fig, ax = plt.subplots(figsize=(8, 3.6))
    for c, col in zip(['지열', '수열', '바이오'], [MAIN, ACC, MUTED]):
        if c in piv: ax.plot(piv.index, piv[c] / piv[c].iloc[0] * 100, '-o', ms=3, color=col, label=c)
    ax.axhline(100, color=INK, lw=.6, ls=':'); ax.set_ylabel('2015년 = 100'); ax.legend(frameon=False); ax.set_title('지열·수열·바이오 생산량 추이 (2015 = 100)', loc='left')
    save('f14_heat_sources.png')
    return out

# ───────── 파트 ② 바이오매스 연료 품질 편차 (15150813) ─────────
def biomass():
    SRC['15150813'] = '한국동서발전(주)_바이오매스 연료분석결과'
    b = csv(15150813)
    for c in ['총수분', '발열량', '회분']: b[c] = num(b[c])
    g = b.groupby('구분').agg(n=('발열량', 'size'), moisture_mean=('총수분', 'mean'), moisture_cv=('총수분', lambda s: s.std() / s.mean()),
                             hv_mean=('발열량', 'mean'), hv_cv=('발열량', lambda s: s.std() / s.mean())).round(3)
    out = dict(samples=int(len(b)), by_type=g.to_dict(orient='index'),
               corr_moisture_heating_value=round(float(b[['총수분', '발열량']].corr().iloc[0, 1]), 3),
               spearman_moisture_heating_value=round(float(b[['총수분', '발열량']].corr(method='spearman').iloc[0, 1]), 3),   # 이상값 1개(발열량 4,930)에 덜 흔들리는 순위 상관
               period=f"{b['성상일자'].min()}~{b['성상일자'].max()}")
    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    for (k, gg), col in zip(b.groupby('구분'), [MAIN, ACC, MUTED, BAD]): ax.scatter(gg['총수분'], gg['발열량'], s=14, color=col, label=k, alpha=.8)
    ax.set_xlabel('총수분 (%)'); ax.set_ylabel('발열량 (kcal/kg)'); ax.legend(frameon=False, fontsize=8)
    ax.set_title(f"바이오 연료: 수분과 발열량 (순위 상관 {out['spearman_moisture_heating_value']:.2f})", loc='left', fontsize=10)
    save('f18_biomass.png')
    return out

# ───────── 파트 ② 원전 계획예방정비와 이용률 (15114951 + nuclear_annual_cf), 사건·고장 (15074543, 15061937), 정비 계획 (15060801) ─────────
def nuclear():
    SRC['15114951'] = '한국수력원자력(주)_원전 호기별 계획예방정비 현황'; SRC['15074543'] = '한국원자력안전기술원_연도별 원전 사고고장 현황'
    SRC['15061937'] = '한국수력원자력(주)_보고대상사건 현황'; SRC['15060801'] = '한국수력원자력(주)_가동원전 호기별 계획예방정비 계획'
    oh = csv(15114951); oh['s'] = pd.to_datetime(oh['시작일'], errors='coerce'); oh['e'] = pd.to_datetime(oh['종료일'], errors='coerce')
    oh = oh.dropna(subset=['s', 'e'])                                  # 날짜가 비어 있는 행(진행 중 등) 제외
    rows = []                                                          # 정비 기간을 연도별 일수로 나눔
    for _, r in oh.iterrows():
        for y in range(r.s.year, r.e.year + 1):
            a, b = max(r.s, pd.Timestamp(y, 1, 1)), min(r.e, pd.Timestamp(y, 12, 31))
            rows.append((r['호기'], y, max(0, (b - a).days + 1)))
    od = pd.DataFrame(rows, columns=['호기', 'y', 'days']).groupby(['호기', 'y']).days.sum().reset_index()
    nc = pd.read_csv(D + 'nuclear_annual_cf_2014_2025.csv'); nc = nc.rename(columns={'년도': 'y', '이용률(퍼센트)': 'cf'})
    j = nc.merge(od, on=['호기', 'y'], how='left').fillna({'days': 0}); j = j[j.y.between(2014, 2025)]
    lo = j[j.cf < 50]
    out = dict(outage_records=int(len(oh)), corr_outage_days_vs_cf=round(float(j[['days', 'cf']].corr().iloc[0, 1]), 3), n=int(len(j)),
               low_cf_cases=int(len(lo)), low_cf_mean_outage_days=round(float(lo.days.mean()), 1), others_mean_outage_days=round(float(j[j.cf >= 50].days.mean()), 1),
               hanbit5={int(y): dict(cf=float(c), outage_days=int(dd)) for y, c, dd in j[j['호기'] == '한빛5호기'][['y', 'cf', 'days']].values if y in (2019, 2020, 2021, 2022, 2023, 2024)})
    ev = csv(15074543); yc = [c for c in ev.columns if re.fullmatch(r'\d{4}', c)]
    out['incidents_by_year'] = {c: int(num(ev[c]).sum()) for c in yc}
    rp = csv(15061937); out['reported_events'] = int(len(rp)); out['reported_events_top_units'] = rp['발생호기'].value_counts().head(5).to_dict()
    pl = csv(15060801); out['planned_outages'] = int(len(pl)); out['planned_outage_days_total'] = round(float(num(pl['총일수']).sum()), 1)
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    ax.scatter(j.days, j.cf, s=10, color=MUTED, alpha=.6, label='호기·연도')
    h5 = j[j['호기'] == '한빛5호기']; ax.scatter(h5.days, h5.cf, s=26, color=BAD, label='한빛 5호기')
    for _, r in h5[h5.cf < 50].iterrows(): ax.annotate(str(int(r.y)), (r.days, r.cf), textcoords='offset points', xytext=(4, 2), fontsize=8, color=BAD)
    ax.set_xlabel('그해 계획예방정비 일수'); ax.set_ylabel('연간 이용률 (%)'); ax.legend(frameon=False, fontsize=8)
    ax.set_title(f"정비 일수와 이용률 (상관 {out['corr_outage_days_vs_cf']:.2f})", loc='left')
    save('f15_nuclear_outage.png')
    return out

# ───────── 파트 ③·④ 2025 시간별 신재생 발전량·설비용량 (15069337): 출력을 누가 정하는가 ─────────
def renewables_hourly():
    SRC['15069337'] = '한국전력거래소_신재생 발전량 및 설비용량'
    r = csv(15069337); r['cap'] = num(r['설비용량']); r['gen'] = num(r['전력거래량(MWh)'])
    r = r[r.cap > 0]; r['cf'] = r.gen / r.cap
    r['t'] = pd.to_datetime(r['거래일자']) + pd.to_timedelta(num(r['시간'].str[:2]) - 1, unit='h')
    r = r.sort_values(['연료원', 't'])
    out = {}
    for k, g in r.groupby('연료원'):
        if g.cap.max() < 50: continue                                 # 설비 50 MW 미만은 제외
        s = g.set_index('t').cf
        pers = (s - s.shift(24)).dropna()
        out[k] = dict(cap_MW=round(float(g.cap.iloc[-1]), 0), cf_mean=round(float(s.mean()), 3), cf_cv_hourly=round(float(s.std() / s.mean()), 3),
                      dayahead_persistence_nRMSE=round(float(np.sqrt((pers ** 2).mean()) * 100), 2))
    sel = [k for k in ['연료전지', '바이오매스', '수력', '소수력', '풍력', '태양광'] if k in out]
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    v = [out[k]['dayahead_persistence_nRMSE'] for k in sel]
    ax.bar(sel, v, color=[MAIN if k in ('연료전지', '바이오매스') else ACC if k in ('태양광', '풍력') else MUTED for k in sel], width=.6)
    for i, x in enumerate(v): ax.text(i, x + .2, f'{x:.1f}%', ha='center', fontsize=9)
    ax.set_ylabel('어제 같은 시각 값으로 예측할 때 오차\n(nRMSE, 설비용량 대비 %)'); ax.set_title('2025년 발전원별 "하루 전 예측의 어려움"', loc='left')
    save('f16_source_variability.png')
    return dict(year=2025, by_source=out)

# ───────── 파트 ③ 출력제어 횟수 (15132422) ─────────
def curtailment():
    SRC['15132422'] = '한국전력거래소_전국 태양광 풍력 제어횟수 및 제주 풍력 제어량'
    z = zipfile.ZipFile(P + '15132422.zip'); out = {}
    for n in z.namelist():
        if not n.endswith('.csv'): continue
        df = pd.read_csv(io.StringIO(text(z.read(n)))); df.columns = [c.strip() for c in df.columns]
        name = re.sub(r'[_ ]*(26년)?\s*상반기|\.csv', '', n).strip()
        y = pd.to_datetime(df['일자'], errors='coerce').dt.year
        out[name] = {int(k): int(v) for k, v in y.value_counts().sort_index().items()}
    fig, ax = plt.subplots(figsize=(7.5, 3.6)); yrs = sorted({y for v in out.values() for y in v}); w = .8 / max(1, len(out))
    for i, (k, v) in enumerate(out.items()):
        ax.bar(np.array(yrs) + (i - (len(out) - 1) / 2) * w, [v.get(y, 0) for y in yrs], w, label=k)
    ax.set_ylabel('출력제어 시행 일수'); ax.legend(frameon=False, fontsize=8); ax.set_title('재생에너지 출력제어 일수 (육지 2026은 상반기, 제주 자료는 2024까지)', loc='left')
    save('f17_curtailment.png')
    return dict(days_by_year=out)

# ───────── 파트 ④ 예측 개선의 돈 가치 (15152008 SMP) — 참고용 단순 환산 ─────────
def value():
    SRC['15152008'] = '한국전력거래소_육지 제주 통합 월별 계통한계가격'
    smp = csv(15152008); smp['y'] = num(smp['년도']); smp['v'] = num(smp['통합계통한계가격'])
    s24 = float(smp[smp.y == 2024].v.mean())
    df = pd.read_csv(D + 'solar_hourly_sido_2020_2024.csv', usecols=['시도명', '발전일자', '설비용량(MW)', '대기권밖일사량계산값'])
    df = df.drop_duplicates(['시도명', '발전일자']); df = df[(df['발전일자'].str[:4] == '2024') & (df['대기권밖일사량계산값'] > 0)]
    cap_hours = float(df['설비용량(MW)'].sum())                         # 2024 낮 시간 설비용량 합(MW·h)
    d_nmae = (R['A']['Persistence']['nMAE'] - R['A']['LightGBM']['nMAE']) / 100
    mwh = d_nmae * cap_hours
    return dict(smp_2024_won_per_kWh=round(s24, 1), daytime_capacity_MWh=round(cap_hours), nMAE_reduction_pp=round(d_nmae * 100, 2),
                abs_error_reduction_GWh=round(mwh / 1000, 1), value_100M_won=round(mwh * 1000 * s24 / 1e8, 1),
                caution='예측 오차가 줄어든 에너지(GWh)에 2024년 평균 SMP를 곱한 단순 환산값. 실제 정산·불균형 비용, 예비력 비용과 다르며 관측 기상 입력 결과 기준이다.')

# ───────── 기타 맥락: 설비용량 구성 (15153657), 신규 보급 (15086290), 중부발전 예방정비 (15140231), 서부발전 고장 유형 (15136947) ─────────
def context():
    SRC['15153657'] = '한국전력거래소_연료원별 일별 설비용량'; SRC['15086290'] = '한국에너지공단_신재생에너지 연도별 신규보급 현황'
    SRC['15140231'] = '한국중부발전(주)_발전소별 예방정비실적 정보'; SRC['15136947'] = '한국서부발전(주)_설비 신뢰성 데이터'
    cap = csv(15153657); cap['v'] = num(cap['설비용량(MW)'])
    out = dict(capacity_2024_MW=cap.set_index('연료원').v.round(0).astype(int).to_dict(), capacity_date=str(cap['거래일'].max()))
    nb = csv(15086290).dropna(how='all'); out['new_install'] = nb.fillna('').astype(str).values.tolist()
    pm = csv(15140231)
    out['komipo_planned_outages'] = dict(count=int(len(pm)), plants=pm['발전소'].value_counts().to_dict(), days_total=int(num(pm['일수']).sum()),
                                         period=f"{pm['시작일'].min()}~{pm['종료일'].max()}",
                                         note='화력·복합 설비만 있고 연료전지·풍력·소수력 정비 기록은 없어 이상 후보 알림과 직접 대조할 수 없다.')
    rel = csv(15136947)
    out['wp_failure_types_top'] = rel['고장유형'].value_counts().head(6).to_dict(); out['wp_failure_records'] = int(len(rel))
    return out

for name, fn in [('geothermal', geothermal), ('heat_sources', heat_sources), ('biomass', biomass), ('nuclear_outage', nuclear),
                 ('renewables_2025', renewables_hourly), ('curtailment', curtailment), ('forecast_value', value), ('context', context)]:
    step(name, fn)
PUB['sources'] = SRC
R['public'] = PUB
def clean(o):                                                      # NaN·inf는 JSON 표준이 아니라 null로 저장(브라우저·Node에서 읽히게)
    if isinstance(o, dict): return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [clean(v) for v in o]
    if isinstance(o, float) and not np.isfinite(o): return None
    if isinstance(o, np.generic): return clean(o.item())
    return o
json.dump(clean(R), open(RJ, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str, allow_nan=False)
print('wrote public:', [k for k in PUB if k != 'sources'], '| 자료', len(SRC), '종')
