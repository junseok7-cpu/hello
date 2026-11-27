"""공공데이터포털 추가 자료 2차(GPT 조사 추천, 13종) 분석
입력: data/public/<포털번호>.csv|zip  (python fetch_data.py --public)
출력: results/results.json 의 'public2' 키, figures/f19~f23
실행: python analyze_public.py 다음에 python analyze_public2.py (약 1~2분)
"""
import io, json, os, zipfile
import numpy as np, pandas as pd, lightgbm as lgb
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
def csv(pk, **kw):
    df = pd.read_csv(io.StringIO(text(open(f'{P}{pk}.csv', 'rb').read())), skipinitialspace=True, **kw)
    df.columns = [c.strip() for c in df.columns]; return df
def zcsvs(pk):
    z = zipfile.ZipFile(f'{P}{pk}.zip')
    for n in z.namelist():
        if n.lower().endswith('.csv'):
            d = pd.read_csv(io.StringIO(text(z.read(n)))); d.columns = [c.strip() for c in d.columns]; yield n, d
def num(s): return pd.to_numeric(s.astype(str).str.replace(',', '').str.strip(), errors='coerce')
def rmse(e): return float(np.sqrt(np.mean(np.square(e))))
def step(name, fn):
    try: OUT[name] = fn(); print('[ok]', name)
    except Exception as e: OUT.setdefault('errors', {})[name] = repr(e); print('[실패]', name, repr(e))

# ───────── ③ 풍력 SCADA: 풍속–출력 곡선 (장흥 15159034, 화순 15159036) ─────────
def wind():
    SRC['15159034'] = '한국서부발전(주)_(AI친화)장흥풍력발전소 스카다 발전 정보'; SRC['15159036'] = '한국서부발전(주)_(AI친화)화순풍력발전소 스카다 발전 정보'
    res, figdat = {}, None
    for pk, name in [(15159034, '장흥풍력'), (15159036, '화순풍력')]:
        d = csv(pk); c = d.columns
        d = pd.DataFrame({'t': pd.to_datetime(d[c[0]].astype(str).str.slice(0, 13), format='%Y-%m-%d %H', errors='coerce'),
                          'unit': d[c[2]], 'ws': num(d[c[3]]), 'p': num(d[c[4]]), 'cap': num(d['발전용량(메가와트)']) * 1000})
        d = d.dropna(subset=['t']).groupby(['unit', 't']).agg(ws=('ws', 'mean'), p=('p', 'mean'), cap=('cap', 'first')).reset_index()   # 10분 → 1시간 평균
        d = d[(d.p >= -50) & (d.ws.between(0, 40))]
        d['cf'] = (d.p / d.cap).clip(0, 1.05)
        d['bin'] = (d.ws / 0.5).round() * 0.5
        yrs = sorted(d.t.dt.year.unique()); test_y = yrs[-1]; tr, te = d[d.t.dt.year < test_y], d[d.t.dt.year == test_y]
        op = tr[tr.cf > 0.01]                                          # 운전 중인 시간만으로 출력 곡선을 만든다(정지·제어 시간 제외)
        cn = op.groupby(['unit', 'bin']).cf.agg(['median', 'size']); cn = cn[cn['size'] >= 30]   # 표본 30시간 미만 구간 제외
        curve = cn['median'].rename('cf_curve').reset_index()
        te = te.merge(curve, on=['unit', 'bin'], how='left').dropna(subset=['cf_curve'])
        te = te.sort_values(['unit', 't'])
        te['lag24'] = te.groupby('unit').cf.shift(24)                  # 하루 전 같은 시각(같은 호기)
        ev = te.dropna(subset=['lag24'])
        r2 = 1 - np.sum((ev.cf - ev.cf_curve) ** 2) / np.sum((ev.cf - ev.cf.mean()) ** 2)
        # 풍속 5~12 m/s 구간: 출력 0(정지·출력제어 의심)과, 운전 중인데 곡선 기대값의 50% 미만(성능 저하 후보)을 나눠 센다
        mid = te[te.ws.between(5, 12)]; stop = mid.cf <= 0.01; low = (mid.cf > 0.01) & (mid.cf < 0.5 * mid.cf_curve)
        res[name] = dict(units=int(d.unit.nunique()), period=f'{d.t.min().date()}~{d.t.max().date()}', test_year=int(test_y), test_hours=int(len(ev)),
                         cf_mean=round(float(d.cf.mean()), 3),
                         nRMSE_persistence_24h=round(rmse(ev.cf - ev.lag24) * 100, 2), nRMSE_curve_with_actual_wind=round(rmse(ev.cf - ev.cf_curve) * 100, 2),
                         r2_power_curve=round(float(r2), 3),
                         windy_hours=int(len(mid)), stopped_hours=int(stop.sum()), stopped_share_pct=round(float(stop.mean() * 100), 2),
                         underperf_hours=int(low.sum()), underperf_share_pct=round(float(low.mean() * 100), 2),
                         stopped_by_unit={str(k): int(v) for k, v in mid.assign(x=stop).groupby('unit').x.sum().items()},
                         underperf_by_unit={str(k): int(v) for k, v in mid.assign(x=low).groupby('unit').x.sum().items()})
        if figdat is None: figdat = (name, tr, curve, te)
    name, tr, curve, te = figdat
    u = tr.unit.value_counts().index[0]; s = tr[tr.unit == u].sample(min(6000, (tr.unit == u).sum()), random_state=0); cu = curve[curve.unit == u]
    fig, axs = plt.subplots(1, 2, figsize=(11, 3.8))
    axs[0].scatter(s.ws, s.cf, s=2, alpha=.25, color=MUTED); axs[0].plot(cu.bin, cu.cf_curve, color=MAIN, lw=2.2, label='출력 곡선(운전 중 구간별 중앙값)')
    tl = te[(te.unit == u) & te.ws.between(5, 12) & (te.cf > 0.01) & (te.cf < 0.5 * te.cf_curve)]; axs[0].scatter(tl.ws, tl.cf, s=5, color=BAD, label='운전 중 곡선 대비 50% 미만(저하 후보)')
    axs[0].set_xlabel('나셀 풍속 (m/s)'); axs[0].set_ylabel('이용률'); axs[0].set_xlim(0, 20); axs[0].legend(frameon=False, fontsize=8); axs[0].set_title(f'{name} {u}호기 풍속–출력', loc='left')
    names = list(res); x = np.arange(len(names))
    axs[1].bar(x - .2, [res[n]['nRMSE_persistence_24h'] for n in names], .4, color=MUTED, label='어제 같은 시각 값')
    axs[1].bar(x + .2, [res[n]['nRMSE_curve_with_actual_wind'] for n in names], .4, color=MAIN, label='실제 풍속 + 출력 곡선')
    for i, n in enumerate(names):
        axs[1].text(i - .2, res[n]['nRMSE_persistence_24h'] + .4, f"{res[n]['nRMSE_persistence_24h']:.1f}", ha='center', fontsize=9)
        axs[1].text(i + .2, res[n]['nRMSE_curve_with_actual_wind'] + .4, f"{res[n]['nRMSE_curve_with_actual_wind']:.1f}", ha='center', fontsize=9)
    axs[1].set_xticks(x, names); axs[1].set_ylabel('nRMSE (설비용량 대비 %)'); axs[1].legend(frameon=False, fontsize=8); axs[1].set_title('풍속을 알면 오차가 얼마나 줄까 (시험 연도)', loc='left')
    save('f19_wind_scada.png')
    return res

# ───────── ③ 제주 풍력: 한경(시간별 2013~, 15043410), 5개 단지 일별(15028181) ─────────
def jeju_wind():
    SRC['15043410'] = '한국남부발전(주)_한경풍력발전실적'; SRC['15028181'] = '제주에너지공사_풍력발전기 전력 정보'
    h = csv(15043410); h['d'] = pd.to_datetime(h['년월일'])
    hh = h.melt(id_vars=['d', '단계'], value_vars=[str(i) for i in range(1, 25)], var_name='h', value_name='p')
    hh['p'] = num(hh.p); hh = hh.groupby(['d', 'h']).p.sum().reset_index(); hh['t'] = hh.d + pd.to_timedelta(hh.h.astype(int) - 1, unit='h')
    s = hh.set_index('t').p.sort_index(); s = s[~s.index.duplicated()].asfreq('h')
    by = {}
    for y, g in s.groupby(s.index.year):
        cap = g.quantile(.999)
        if cap <= 0 or g.notna().sum() < 2000: continue
        e = (g - s.shift(24).reindex(g.index)) / cap; by[int(y)] = round(rmse(e.dropna()) * 100, 2)
    j = csv(15028181); j['d'] = pd.to_datetime(j.iloc[:, 0], errors='coerce'); sites = [c for c in j.columns[1:] if c not in ('전체', 'd')]
    for c in sites: j[c] = num(j[c])
    rel = j[sites].div(j[sites].max())                                 # 단지별 최대값으로 정규화
    peer = rel.apply(lambda r: r.median(), axis=1)
    ratio = rel.div(peer.replace(0, np.nan), axis=0)
    return dict(hangyeong_years=f'{min(by)}~{max(by)}', hangyeong_persistence_nRMSE_by_year=by,
                jeju_sites=sites, jeju_days=int(j.d.notna().sum()), jeju_period=f'{j.d.min().date()}~{j.d.max().date()}',
                jeju_peer_low_days={c: int((ratio[c] < 0.3).sum()) for c in sites},
                note='제주 5개 단지는 같은 날 단지끼리 비교(자기 최대값 대비 비율 ÷ 단지 중앙값). 0.3 미만인 날을 저하 후보로 셈. 기간이 짧아 참고용')

# ───────── ③④ 한수원 태양광 발전소별 시간별 + 기상 (15165984): 발전소 단위 검증 ─────────
def khnp_solar():
    SRC['15165984'] = '한국수력원자력(주)_(AI친화고가치)기상정보를 융합한 한수원 태양광 시계열 발전정보'
    d = pd.concat([x for _, x in zcsvs(15165984)])
    d['t'] = pd.to_datetime(d['거래일']) + pd.to_timedelta(num(d['시간']) - 1, unit='h')
    for c in ['설비용량', '계량전력량', '기온', '강수량', '풍속', '습도', '일조', '일사']: d[c] = num(d[c])
    d = d[d['설비용량'] > 0].drop_duplicates(['발전기코드', 't']).sort_values(['발전기코드', 't'])
    d['cf'] = (d['계량전력량'] / d['설비용량']).clip(0, 1.05)            # 설비용량 kW, 계량전력량 kWh(1시간)
    d['lag24'] = d.groupby('발전기코드').cf.shift(24); d['lag168'] = d.groupby('발전기코드').cf.shift(168)
    hr, doy = d.t.dt.hour, d.t.dt.dayofyear
    d['hs'], d['hc'], d['ds'], d['dc'] = np.sin(2*np.pi*hr/24), np.cos(2*np.pi*hr/24), np.sin(2*np.pi*doy/366), np.cos(2*np.pi*doy/366)
    d['plant'] = d['발전기코드'].astype('category').cat.codes
    d = d[hr.between(6, 19)]                                          # 낮 시간만
    tr, te = d[d.t.dt.year <= 2024], d[d.t.dt.year == 2025]
    base = ['hs', 'hc', 'ds', 'dc', 'plant', 'lag24', 'lag168']
    sets = {'기상 없음': base, '예보 항목(기온·습도·풍속·강수)': base + ['기온', '습도', '풍속', '강수량'], '+ 실측 일조·일사': base + ['기온', '습도', '풍속', '강수량', '일조', '일사']}
    ev = te.dropna(subset=['lag24', 'cf']); out = {'persistence': round(rmse(ev.cf - ev.lag24) * 100, 2)}
    for k, cols in sets.items():
        m = lgb.LGBMRegressor(n_estimators=400, learning_rate=0.05, num_leaves=63, verbose=-1, random_state=0).fit(tr[cols], tr.cf, categorical_feature=['plant'])
        out[k] = round(rmse(ev.cf - pd.Series(m.predict(ev[cols]), index=ev.index).clip(0, 1)) * 100, 2)
    sk = {k: round(1 - v / out['persistence'], 3) for k, v in out.items() if k != 'persistence'}
    fig, ax = plt.subplots(figsize=(7, 3.4)); ks = ['persistence'] + list(sets); lab = ['어제 값', '기상 없음', '예보 항목', '+ 실측 일사']
    ax.bar(lab, [out[k] for k in ks], color=[MUTED, MUTED, MAIN, ACC], width=.6)
    for i, k in enumerate(ks): ax.text(i, out[k] + .2, f'{out[k]:.1f}%', ha='center', fontsize=9)
    ax.set_ylabel('nRMSE (설비용량 대비 %)'); ax.set_title(f'발전소 단위에서도 같은 결론 — 한수원 태양광 {d["발전기코드"].nunique()}곳, 2025년 낮', loc='left', fontsize=10)
    save('f21_khnp_solar.png')
    return dict(plants=int(d['발전기코드'].nunique()), plant_names=sorted(d['발전기명'].unique().tolist())[:12], period=f'{d.t.min().date()}~{d.t.max().date()}',
                train='2023~2024', test='2025', test_hours=int(len(ev)), nRMSE=out, Skill_vs_persistence=sk,
                note='기상은 발전소 인근 관측값. "예보 항목"은 예보에도 있는 항목만 썼다는 뜻이지 실제 예보는 아니다.')

# ───────── ② 화력·발전 호기별 월별 열효율·이용률 (동서발전 15083316) ─────────
def ewp_units():
    SRC['15083316'] = '한국동서발전(주)_(발전공기업 표준) 발전실적 정보'
    d = csv(15083316); d['ym'] = pd.to_datetime(d['연월'], errors='coerce')
    for c in ['설비용량(메가와트)', '발전량(메가와트시)', '열효율(퍼센트)', '이용률(퍼센트)']: d[c] = num(d[c])
    th = d[d['열효율(퍼센트)'] > 0].copy()
    th['key'] = th['발전소명'] + ' ' + th['호기'].astype(str)
    by = th.groupby('발전원').agg(units=('key', 'nunique'), eff_median=('열효율(퍼센트)', 'median'), cf_median=('이용률(퍼센트)', 'median')).round(1)
    th = th.sort_values(['key', 'ym'])
    th['base'] = th.groupby('key')['열효율(퍼센트)'].transform(lambda s: s.shift(1).rolling(12, min_periods=6).median())
    th['drop'] = (th.base - th['열효율(퍼센트)']) >= 2.0                # 최근 12개월 중앙값보다 열효율이 2%p 이상 낮은 달
    yr = th.groupby([th.ym.dt.year, '발전원'])['열효율(퍼센트)'].median().unstack().round(1)
    return dict(period=f"{d.ym.min():%Y-%m}~{d.ym.max():%Y-%m}", by_source=by.to_dict(orient='index'), eff_by_year=yr.to_dict(),
                eff_drop_unit_months=int(th['drop'].sum()), judged_unit_months=int(th.base.notna().sum()),
                top_drop_units=th[th['drop']].key.value_counts().head(5).to_dict())

# ───────── ② 연료전지 월별 실적 (남부발전 15095396): 장기 저하가 흔한가 ─────────
def kospo_fuelcell():
    SRC['15095396'] = '한국남부발전(주)_연료전지 발전실적'
    d = csv(15095396); d['ym'] = pd.to_datetime(d['발전년월'], errors='coerce')
    d['cap'], d['gen'] = num(d['용량(MW)']), num(d['발전량(MWh)'])
    d['cf'] = d.gen / (d.cap * d.ym.dt.days_in_month * 24); d['key'] = d['발전소명'] + ' ' + d['단계'].astype(str)
    bad = int((d.cf > 1.05).sum()); d = d[d.cf.between(0.05, 1.05)]          # 증설 시기 용량·발전량 불일치(이용률 1 초과) 제외
    out = {}
    for k, g in d.dropna(subset=['cf']).groupby('key'):
        a = g.groupby(g.ym.dt.year).cf.median()
        if len(a) < 3: continue
        x = np.array(a.index, float); slope = np.polyfit(x, a.values, 1)[0]
        out[k] = dict(years=f'{int(x.min())}~{int(x.max())}', cf_first=round(float(a.iloc[0]), 3), cf_last=round(float(a.iloc[-1]), 3), slope_pp_per_year=round(float(slope * 100), 2))
    fig, ax = plt.subplots(figsize=(8, 3.6))
    for k, g in d.dropna(subset=['cf']).groupby('key'): ax.plot(g.ym, g.cf.rolling(3, min_periods=1).median(), lw=1.2, label=k)
    ax.set_ylabel('월 이용률 (3개월 중앙값)'); ax.legend(frameon=False, fontsize=7, ncol=2); ax.set_title('남부발전 연료전지 — 해가 갈수록 이용률이 떨어지는가', loc='left')
    save('f22_fuelcell_trend.png')
    dec = [k for k, v in out.items() if v['slope_pp_per_year'] < -1]
    return dict(plants=out, declining_over_1pp_per_year=dec, n=len(out), excluded_cf_over_1=bad,
                note='단계 증설 시기에는 용량과 발전량 기준이 어긋나 이용률이 1을 넘는 달이 있어 제외했다. 단계 묶음이 바뀌면 다른 계열로 본다.')

# ───────── ① 지열·수열: 충남개발공사 건물 지열 월별(15118844), 외기온도와 열생산·수열(15164288) ─────────
def heat_more():
    SRC['15118844'] = '충청남도개발공사_에너지 사용현황'; SRC['15164288'] = '한국지역난방공사_외기온도에 따른 전체 열생산량 대비 타사 수열량 데이터'
    g = csv(15118844); gc = [c for c in g.columns if '지열' in c and c[:4].isdigit()]
    gm = g[['월'] + gc].copy(); gm.columns = ['월'] + [c[:4] for c in gc]
    for c in gm.columns[1:]: gm[c] = num(gm[c])
    yearly = gm.iloc[:, 1:].sum().round(0).astype(int).to_dict()
    mm = gm.set_index('월').iloc[:, :-1].mean(axis=1); prof = (mm / mm.mean()).round(2).to_dict()
    w = csv(15164288); temp = num(w.iloc[:, -1]); tot = num(w.iloc[:, -2]); ext = num(w['수열 총계'])
    ok = temp.notna() & tot.notna()
    return dict(chungnam_geothermal_yearly=yearly, chungnam_geothermal_month_index=prof,
                kdhc_days=int(len(w)), kdhc_corr_temp_total_heat=round(float(np.corrcoef(temp[ok], tot[ok])[0, 1]), 3),
                kdhc_external_heat_share_pct=round(float((ext / tot).median() * 100), 1))

# ───────── ② 제주 연료원별 시간대 실적 (15161308): 제주에서 누가 수요를 따라가나 ─────────
def jeju_fuel():
    SRC['15161308'] = '한국전력거래소_제주발전기 연료원 시간대별 전력거래량'
    frames = []
    for n, d in zcsvs(15161308):
        d = d.rename(columns=str.upper); frames.append(d[['TRAD_YMD', 'TRAD_HH', 'FUEL_NM', 'AMGO']])
    d = pd.concat(frames); d['AMGO'] = num(d.AMGO)
    p = d.pivot_table(index=['TRAD_YMD', 'TRAD_HH'], columns='FUEL_NM', values='AMGO', aggfunc='sum').fillna(0)
    p['합계'] = p.sum(axis=1); yy = pd.Series(p.index.get_level_values(0).astype(str).str[:4].astype(int), index=p.index)
    last = p[yy == yy.max()]
    corr = {str(c): round(float(last[c].corr(last['합계'])), 3) for c in last.columns if c != '합계' and last[c].sum() > 0.01 * last['합계'].sum()}
    ren = [c for c in p.columns if any(k in str(c) for k in ('태양', '풍력', '급전가능 재생'))]   # 2024년부터 대형 풍력 등이 '급전가능 재생에너지'로 분류가 옮겨감
    share = (p[ren].sum(axis=1).groupby(yy).sum() / p['합계'].groupby(yy).sum() * 100).round(1)
    fig, ax = plt.subplots(figsize=(7.5, 3.4)); ax.plot(share.index, share.values, '-o', ms=3, color=ACC)
    ax.set_ylabel('태양광+풍력(+급전가능 재생) 비중 (%)'); ax.set_title('제주 전력거래량 중 태양광·풍력 비중', loc='left')
    save('f23_jeju_renewable_share.png')
    return dict(years=f'{yy.min()}~{yy.max()}', fuels=[str(c) for c in p.columns if c != '합계'], corr_with_total_last_year=corr,
                renewable_share_pct_by_year={int(k): float(v) for k, v in share.items()}, renewable_cols=[str(c) for c in ren])

# ───────── 기타: 소수력 잠재량(15121931), 바이오가스 자체활용(15149686), 지역난방 예방정비(15131797) ─────────
def misc():
    SRC['15121931'] = '한국수자원공사_소수력 잠재 발전 가능량 데이터'; SRC['15149686'] = '경기도 부천시_공공하수처리시설 바이오가스 자체활용 현황'
    SRC['15131797'] = '한국지역난방공사_플랜트관리 예방정비 관리 실적'
    h = csv(15121931); h['유량'], h['발전량'] = num(h['유량']), num(h['발전량'])
    b = csv(15149686); gen = num(b['발전기']); tot = num(b['합 계'])
    m = csv(15131797)
    return dict(smallhydro_records=int(len(h)), smallhydro_basins=int(h['표준유역명'].nunique()), smallhydro_corr_flow_power=round(float(h[['유량', '발전량']].corr().iloc[0, 1]), 3),
                biogas_generator_share_pct=round(float(gen.sum() / tot.sum() * 100), 1), biogas_generator_month_cv=round(float(gen.std() / gen.mean()), 3),
                kdhc_pm_records=int(len(m)), kdhc_pm_results=m['정비결과'].value_counts().to_dict())

for name, fn in [('wind_scada', wind), ('jeju_wind', jeju_wind), ('khnp_solar', khnp_solar), ('ewp_units', ewp_units),
                 ('kospo_fuelcell', kospo_fuelcell), ('heat_more', heat_more), ('jeju_fuel', jeju_fuel), ('misc', misc)]:
    step(name, fn)
OUT['sources'] = SRC
R['public2'] = OUT
def clean(o):                                                      # NaN·inf는 JSON 표준이 아니라 null로 저장(브라우저·Node에서 읽히게)
    if isinstance(o, dict): return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [clean(v) for v in o]
    if isinstance(o, float) and not np.isfinite(o): return None
    if isinstance(o, np.generic): return clean(o.item())
    return o
json.dump(clean(R), open(RJ, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str, allow_nan=False)
print('wrote public2:', [k for k in OUT if k != 'sources'], '| 자료', len(SRC), '종')
