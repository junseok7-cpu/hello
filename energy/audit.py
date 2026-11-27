"""받은 데이터 10종 점검. 결과: results/data_audit.json"""
import pandas as pd, numpy as np, json
D='data/'; A={}
def s(x): return {k:(float(v) if isinstance(v,(np.floating,float)) else int(v) if isinstance(v,(np.integer,)) else v) for k,v in x.items()}
# 1 태양광 시간별
df=pd.read_csv(D+'solar_hourly_sido_2020_2024.csv'); df.columns=[c.strip() for c in df.columns]
df['t']=pd.to_datetime(df['발전일자'])
dup=df.duplicated(['시도명','t'],keep=False); dd=df[dup]
conf=dd.groupby(['시도명','t'])['발전량(MWh)'].agg(lambda x:x.max()-x.min())
day=df['대기권밖일사량계산값']>0
u=df.drop_duplicates(['시도명','t'])
full=pd.date_range('2020-01-01','2024-12-31 23:00',freq='h')
miss_ts={r:int(len(full)-g.t.nunique()) for r,g in u.groupby('시도명')}
cf=u['발전량(MWh)']/u['설비용량(MW)']
nightshare=(u.loc[u['대기권밖일사량계산값']==0,'발전량(MWh)'].sum()/u['발전량(MWh)'].sum())
A['solar_hourly']=s(dict(rows=len(df),regions=int(df['시도명'].nunique()),period=f"{df.t.min()}~{df.t.max()}",
  dup_rows=int(df.duplicated(['시도명','t']).sum()),dup_rows_exact=int(df.duplicated().sum()),dup_keys_value_differs=int((conf>1e-6).sum()),dup_max_abs_diff_MWh=float(conf.max()),
  missing_timestamps_by_region=miss_ts,
  daytime_missing_ghi=float(u.loc[u['대기권밖일사량계산값']>0,'일사량'].isna().mean()),
  daytime_missing_gen=float(u.loc[u['대기권밖일사량계산값']>0,'발전량(MWh)'].isna().mean()),
  cf_over_1=int((cf>1).sum()),neg_gen=int((u['발전량(MWh)']<0).sum()),
  ghi_over_extra=int((u['일사량']>u['대기권밖일사량계산값']+0.01).sum()),
  night_gen_share_total=float(nightshare)))
# 2 중부발전 발전소별 일별
k=pd.read_csv(D+'komipo_plants_daily_2023_2026.csv'); k.columns=[c.strip() for c in k.columns]
k['type']=np.select([k['발전설비'].str.contains('태양'),k['발전설비'].str.contains('풍력'),k['발전설비'].str.contains('연료')],['태양광','풍력','연료전지'],'기타')
k['cf']=k['발전량']/(k['설비용량']*24)
A['komipo_daily']=s(dict(rows=len(k),plants=int(k['발전설비'].nunique()),types=k.groupby('type')['발전설비'].nunique().to_dict(),
  period=f"{k['연월일'].min()}~{k['연월일'].max()}",dup=int(k.duplicated(['연월일','발전설비']).sum()),
  cf_median_by_type=k.groupby('type').cf.median().round(3).to_dict(),cf_over_1=int((k.cf>1).sum()),zero_days=int((k['발전량']==0).sum()),
  neg=int((k['발전량']<0).sum()),missing=int(k['발전량'].isna().sum()),unit_note='설비용량 kW, 발전량 kWh/일로 보면 이용률이 타당한 범위'))
A['komipo_plants']=k.groupby(['type','발전설비'])['설비용량'].max().reset_index().values.tolist()
# 3 연료원별 일별
f=pd.read_csv(D+'fuel_daily_region_2018_2022.csv'); f.columns=[c.strip() for c in f.columns]
A['fuel_daily']=s(dict(rows=len(f),period=f"{f['거래일자'].min()}~{f['거래일자'].max()}",fuels=f['연료원'].value_counts().to_dict(),regions=int(f['지역'].nunique()),
  dup=int(f.duplicated(['거래일자','지역','연료원']).sum()),neg=int((f['발전량(MWh)']<0).sum()),days=int(f['거래일자'].nunique())))
# 4 화력 호기별
th=pd.read_csv(D+'thermal_units_daily_2022_2023.csv'); th.columns=[c.strip() for c in th.columns]
A['thermal_units']=s(dict(rows=len(th),period=f"{th['운전일'].min()}~{th['운전일'].max()}",units=th.groupby(['사업소명'])['호기'].nunique().to_dict(),
  max_over_cap=int((th['최대 발전량']/1000>th['용량']*1.05).sum()),note='최대/최소 발전량은 kW로 보임(용량 MW×1000 이하)'))
# 5 수요
dm=pd.read_csv(D+'demand_hourly_2017_2021.csv'); v=dm.iloc[:,1:]
A['demand_hourly']=s(dict(days=len(dm),period=f"{dm.iloc[0,0]}~{dm.iloc[-1,0]}",missing=int(v.isna().sum().sum()),min_MW=float(v.min().min()),max_MW=float(v.max().max()),
  expected_days=int(len(pd.date_range(dm.iloc[0,0],dm.iloc[-1,0])))))
# 6 2025 수급
sp=pd.read_csv(D+'supply_daily_2025.csv'); sp.columns=[c.strip() for c in sp.columns]
chk=(sp['공급능력']-sp['최대전력']-sp['공급예비']).abs().max(); chk2=(sp['공급예비']/sp['최대전력']*100-sp['공급예비율']).abs().max()
A['supply_2025']=s(dict(days=len(sp),reserve_identity_maxdiff=float(chk),reserve_rate_maxdiff=float(chk2),
  peak_max=float(sp['최대전력'].max()),peak_max_day=str(sp.loc[sp['최대전력'].idxmax(),'일자']),min_reserve_rate=float(sp['공급예비율'].min()),min_reserve_day=str(sp.loc[sp['공급예비율'].idxmin(),'일자'])))
# 7 원전
nc=pd.read_csv(D+'nuclear_annual_cf_2014_2025.csv'); ng=pd.read_csv(D+'nuclear_annual_gen_2019_2025.csv')
A['nuclear']=s(dict(cf_rows=len(nc),cf_over_100=nc[nc['이용률(퍼센트)']>100][['호기','년도','이용률(퍼센트)']].values.tolist()[:40],n_over100=int((nc['이용률(퍼센트)']>100).sum())))
ng2=ng.melt(id_vars=['구분','호기'],value_vars=[c for c in ng.columns if '년 발전량' in c]); ng2['년도']=ng2.variable.str[:4].astype(int)
ng2['호기명']=ng2['구분']+ng2['호기'].str.replace('#','')+'호기'
mm=ng2.merge(nc,left_on=['호기명','년도'],right_on=['호기','년도'],how='inner')
A['nuclear']['gen_files_matched_rows']=int(len(mm)); A['nuclear']['gen_files_max_abs_diff_MWh']=float((mm['value']-mm['발전량(MWh)']).abs().max())
A['nuclear']['unmatched_names']=sorted(set(ng2.loc[ng2.value>0,'호기명'])-set(nc['호기']))
# 8 예측 하루치
kf=pd.read_csv(D+'kpx_solar_forecast_20241202.csv')
tot=kf[['계량 태양광 발전량 예측값(MWh)','소비자발전 태양광 발전량 예측값(MWh)','전력구매계약 태양광 발전량 예측값(MWh)']].sum(1)
cap=kf.drop_duplicates('시도명')[['계량 태양광 설비용량(MW)','소비자발전 태양광 설비용량 추정값(MW)','전력구매계약 태양광 설비용량 추정값(MW)','전체 태양광 설비용량(MW)']].sum()
A['kpx_forecast']=s(dict(rows=len(kf),sum_identity_maxdiff=float((tot-kf['태양광 발전량 예측값 총합(MWh)']).abs().max()),
  capacity_MW=cap.round(0).to_dict(),metered_share=float(cap.iloc[0]/cap.iloc[3]),issued=f"{kf['기준일자'][0]} {kf['기준시각'][0]}",target=str(kf['예측일자'][0])))
# 9 지역 연평균
rg=pd.read_csv(D+'regional_annual_avg_2018_2025.csv'); A['regional_annual']=dict(table=rg.fillna('').values.tolist(),note='발전원 미상(파일명 깨짐), 전라도 2018~19 빈칸')
json.dump(A,open('results/data_audit.json','w'),ensure_ascii=False,indent=1,default=str)
print(json.dumps({k:v for k,v in A.items() if k!='komipo_plants'},ensure_ascii=False,indent=1,default=str))
