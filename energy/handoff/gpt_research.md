## 1. 조사 요약

3일 안에는 **① 태양광 예측의 발행 시각을 고정하고 ② 예측구간의 보정 기간을 분리한 뒤 ③ 연료전지에 지속 저하 알림을 추가**하는 순서가 좋습니다. 세 가지 모두 기존 CSV로 구현할 수 있습니다. 기존 태양광 nRMSE 6.05%는 **관측 기상 입력 기준**으로 제시하고, LNG와 풍력·소수력 결과는 원 데이터 실행 후 평가 일수·결측·그림을 확인하기 전까지 **검증 대기**로 둡니다.

### 태양광 하루 전 예측

- 하루 전 태양광 예측에는 수치기상예보를 발전량으로 변환하는 물리 모델, 기상과 과거 발전량을 쓰는 통계·머신러닝 모델, 두 접근을 결합하는 모델이 쓰입니다. [IEA PVPS 태양광 자원 핸드북, 9장](https://iea-pvps.org/wp-content/uploads/2024/09/Best-Practices-Handbook-for-the-Collection-and-Use-of-Solar-Resource-Data-for-Solar-Energy-Applications-Fourth-Edition-.pdf)
- 기준선은 과거 같은 시각의 발전량을 그대로 쓰는 **지속성 예측**과, 맑은 하늘 일사량의 변화로 보정하는 **스마트 지속성 예측**이 대표적입니다. 첨부 데이터의 `extra`는 대기권 밖 일사량이므로 지표의 맑은 하늘 일사량과 구분해야 합니다. [IEA PVPS 태양광 자원 핸드북, 9장](https://iea-pvps.org/wp-content/uploads/2024/09/Best-Practices-Handbook-for-the-Collection-and-Use-of-Solar-Resource-Data-for-Solar-Energy-Applications-Fourth-Edition-.pdf)
- 첨부 코드에서 전날 14시를 발행 시각으로 잡으면, `lag24`의 전날 오후 일부 값과 예측 대상일의 관측 기상은 발행 후에 생깁니다. 기존 결과와 함께 `lag48`, `lag168`, 달력, `extra`만 사용하는 발행 시각 기준 실험을 제시할 수 있습니다. 지연값의 실제 공개 시각과 발전량 시간표기 기준은 **확인 필요**입니다.

### 확률 예측

- 분위수 회귀는 P10과 P90을 직접 추정합니다. 분위수 회귀에 컨포멀 보정을 결합한 CQR은 모델 선택에 쓰지 않은 보정 표본의 오차 순위를 이용해 구간을 조정합니다. [Romano 외, CQR](https://proceedings.neurips.cc/paper_files/paper/2019/hash/5103c3584b063c431bd1268e9b5e76fb-Abstract.html)
- 구간은 **포함률·평균 폭·구간 점수**를 같이 봅니다. 구간 점수는 폭이 넓거나 실측이 구간 밖으로 멀어질수록 커집니다. 월별 포함률과 표본 수도 함께 보면 연간 평균이 가리는 편차를 확인할 수 있습니다. [Gneiting·Raftery, 구간 점수](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf)
- 첨부 코드는 2023년 전체를 조기 종료와 구간 보정에 함께 씁니다. 상반기와 하반기를 시간순으로 분리하고 2024년 포함률을 실측합니다. 인접 시간과 지역의 오차가 서로 연관될 수 있으므로 **80%는 목표 포함률**로 발표합니다. [Romano 외, CQR](https://papers.neurips.cc/paper/8613-conformalized-quantile-regression.pdf), [Xu·Xie, 시계열 컨포멀 예측](https://proceedings.mlr.press/v139/xu21h.html)

### 이상탐지

- 과거 중앙값과 MAD(중앙값 절대편차)는 큰 이탈일을 찾는 데 적합합니다. 지속적인 작은 하락에는 **CUSUM(누적합)**이나 **EWMA(최근 값에 더 큰 가중치를 주는 이동평균)**처럼 여러 날의 신호를 합치는 방법을 씁니다. [NIST, CUSUM](https://itl.nist.gov/div898/handbook/pmc/section3/pmc3231.htm), [NIST, EWMA](https://itl.nist.gov/div898/handbook/mpc/section2/mpc2211.htm)
- 연료전지는 빠르게 움직이는 28일 기준선이 장기 저하를 따라 내려갈 수 있습니다. 초기 기준선을 고정한 하방 CUSUM을 기존 급락 알림 옆에 두고, 결측일에는 누적을 끊습니다. 기준 기간의 정상 운전 여부는 **확인 필요**입니다.
- 태양광 인접 비교는 대상 발전소를 기준 중앙값에서 빼고 같은 날의 유효 동료 수를 확인합니다. 풍력·소수력은 바람·유량 변화가 발전량에 영향을 주므로, 일별 발전량으로 찾은 신호는 모두 **이상 후보 알림**으로 보고합니다. [IEA PVPS 태양광 운영·정비 가이드](https://pvpmc.sandia.gov/app/uploads/sites/243/dlm_uploads/2022/12/IEA-PVPS-Report-T13-25-2022-OandM-Guidelines.pdf)

### LNG·수요 추종 예측

- 단기 전력수요는 달력, 기온, 과거 수요를 입력으로 쓰는 회귀와 시계열 모형이 대표적입니다. 현재 CSV로는 달력과 과거 수요를 활용할 수 있습니다. [Fan·Hyndman, GEFCom2014 수요 예측](https://doi.org/10.1016/j.ijforecast.2015.11.010)
- LNG 발전량에는 수요와 다른 발전원의 가용 용량, 발전비용 등 급전 조건이 함께 작용합니다. 국내 데이터의 수요–LNG 상관은 동행 관계를 설명하는 자료로 쓰고, 예측 성능은 시간순 시험으로 별도 평가합니다. [EIA 전력시장 급전 모형 문서](https://www.eia.gov/outlooks/aeo/nems/documentation/electricity/pdf/EMM_AEO2025.pdf)
- `lag1`과 `lag7`을 기준선으로 두고, **같은 날짜에서 수요를 뺀 모델과 전날 수요를 넣은 모델**을 비교하면 수요 피처의 추가 기여를 확인할 수 있습니다. 당일 관측 수요는 사후 참고용입니다. 전날 수요와 LNG 집계가 발행 시각에 도착하는지는 **확인 필요**입니다. [Hyndman·Athanasopoulos, 시간순 교차검증과 기준선](https://otexts.com/fpp3/toolbox.html)

## 2. 보완안 표

외부 연구 수치는 해당 연구의 실험 결과입니다. 아래 변경이 팀 데이터에서 얼마나 개선되는지는 **확인 필요**입니다.

| 번호 | 대상 | 방법 | 기대 효과(근거 출처) | 구현 난이도 | 필요한 데이터 | 발표에서 얻는 점 |
|---|---|---|---|---|---|---|
| **1** | 태양광 점 예측 | 전날 14시 발행 가정. `lag48`·`lag168`·달력·`extra` LightGBM을 같은 시각 기준선 및 관측 입력 모델과 공통 행에서 비교 | 발행 시각에 맞춘 오차를 측정. 참고로 별도 연구에서 실제 수치기상예보를 쓴 하루 전 모델의 RMSE 기반 스킬은 지속성 대비 2020년 32.6%, 2021년 35.5%였음. [Koster 외, 표 1](https://doi.org/10.1002/solr.202200652) | 하 | 기존 태양광 시간별 CSV | 관측 조건 성능과 발행 시각 기준 성능을 한 표에서 비교 |
| **2** | 태양광 확률 예측 | 조기 종료와 보정 기간 분리, 분위수 교차 정렬, 순위 기반 CQR 보정, 월별 진단 | 원 논문의 11개 데이터셋 평균에서 90% 목표 CQR 랜덤포레스트는 평균 폭 1.40·포함률 90.34%, 일반 split-conformal 랜덤포레스트는 폭 2.24·포함률 90.00%. 팀의 80% 시계열 구간 효과는 확인 필요. [Romano 외, 표 1](https://papers.neurips.cc/paper/8613-conformalized-quantile-regression.pdf) | 중 | 1번과 동일 | 포함률을 맞추는 과정에서 구간이 얼마나 넓어졌는지 설명 |
| **3** | 연료전지 | 초기 기준선 대비 하방 CUSUM을 기존 급락 규칙에 추가 | NIST 표에서 기준 이동량 `k=0.5`, 임계값 `h=4`일 때 1σ 평균 이동의 평균 신호 길이는 8.38표본. 발전소 데이터의 탐지 지연과 오경보율은 확인 필요. [NIST CUSUM 표](https://itl.nist.gov/div898/handbook/pmc/section3/pmc3231.htm) | 하 | 기존 중부발전 발전소 일별 CSV | 급락과 작은 저하의 누적을 같은 발전소 시계열에서 설명 |
| 4 | LNG | 동일 `tr`·`te`에서 달력+`lag1/7`과 여기에 전날 수요를 더한 선형회귀·GBDT 비교. 집계 지연을 가정한 이틀 전 입력은 선택 | 모델 복잡도와 수요 피처의 기여를 구분. 국내 LNG 개선 폭은 확인 필요. [GEFCom2014 수요 예측](https://doi.org/10.1016/j.ijforecast.2015.11.010) | 하 | 기존 LNG 발전량·시간별 수요 CSV | `lag1`·`lag7`을 이기는지, 전날 수요가 추가로 도움이 되는지 답변 |
| 5 | 태양광 발전소 비교 | 대상 설비 제외 중앙값, 같은 날 유효 동료 2기 이상, 지역 동료 부족일은 판정 보류 | 대상 설비의 값이 자기 기준에 들어가는 문제를 줄임. 경보 건수와 오경보 변화는 확인 필요. [IEA PVPS 운영·정비 가이드](https://pvpmc.sandia.gov/app/uploads/sites/243/dlm_uploads/2022/12/IEA-PVPS-Report-T13-25-2022-OandM-Guidelines.pdf) | 하 | 기존 중부발전 CSV·지역 매핑 | 알림 건수와 함께 지역 내 비교가 가능했던 일수를 제시 |
| 6 | 풍력·소수력 | 기존 절대·상대 하락 규칙의 판정 가능 일수와 결측일을 먼저 검증. 0발전 연속 구간을 별도로 표시 | 발전이 실제 0으로 기록된 날과 관측 자체가 없는 날을 구분. 고장 검출 성능은 확인 필요. [NIST 공정 모니터링](https://itl.nist.gov/div898/handbook/mpc/section2/mpc22.htm) | 하 | 기존 중부발전 CSV | 알림 0건을 해석할 때 관측 범위와 규칙의 한계를 함께 설명 |
| 7 | 태양광 실제 예보 입력 **선택** | 기상청 API허브에서 2024-12-02 대상의 전날 발행 예보와 지역 매핑을 소량 확인 | 당시 발행본을 확보할 수 있는지 검증. 2020~2024년 동일 피처·격자·예보시간의 확보 가능성과 호출량은 확인 필요. [기상청 API허브](https://apihub.kma.go.kr/apiList.do?seqApi=10) | 중 | 선택 추가 데이터인 과거 단기예보 | 운영 입력의 출처를 시연. 하루 자료는 연결 확인에 적합 |

## 3. 우선순위 상위 3개 구현 코드

아래 블록은 첨부 `analyze.py`에 넣는 제안입니다. 새 키를 `R`에 추가하므로 마지막 `json.dump`에서 저장됩니다. **파일은 수정하지 않았으며, 원 CSV에서 실행한 수치는 없습니다.** 코드의 2023년 분할과 CUSUM 임계값은 3일 일정에 맞춰 제안한 실험 설정입니다.

### ① 태양광 발행 시각 기준 평가

**삽입 위치**는 기존 확률 예측 블록의 `log('interval', R['interval'])` 직후입니다. **저장 키는 `solar_issue_14`**입니다.

목표일 전날 14시를 가정하고, 모든 목표 시각에 동일하게 적용하기 쉬운 48시간·168시간 지연값을 씁니다. 48시간 전 발전량이 발행 전에 확보된다는 가정은 남습니다. `extra > 0`은 발전량·관측 일사량을 보지 않고 평가할 낮 시간을 정합니다. 기존 `p_main`은 **관측 기상과 `lag24`를 쓰는 참고 모델**로 같은 행에서 다시 채점합니다. 따라서 세 모델의 차이는 입력 조건 전체의 차이이며, 기상만의 효과로 해석할 수 없습니다.

```python
lag48_source = df[['시도명', 't', 'cf']].rename(columns={'cf': 'lag48'})
lag48_source['t'] += pd.Timedelta(hours=48)
df['lag48'] = (
    lag48_source.set_index(['시도명', 't'])['lag48']
    .reindex(pd.MultiIndex.from_frame(df[['시도명', 't']]))
    .to_numpy()
)

issue_cols = TIME + ASTRO + ['lag48', 'lag168']
solar_ok = df.extra.gt(0) & np.isfinite(df.cf) & df.cap.gt(0)
solar_2023_h1 = VA & df.t.dt.month.le(6)
issue_ev = TE & solar_ok & df.lag48.notna()

def fit_issue(alpha=None):
    train = TR & solar_ok
    stop = solar_2023_h1 & solar_ok
    params = dict(
        n_estimators=3000, learning_rate=0.05, num_leaves=63,
        min_child_samples=50, subsample=0.8, subsample_freq=1,
        colsample_bytree=0.8, random_state=0, verbose=-1
    )
    if alpha is not None:
        params.update(objective='quantile', alpha=alpha)
    return lgb.LGBMRegressor(**params).fit(
        df.loc[train, issue_cols], df.loc[train, 'cf'],
        eval_set=[(df.loc[stop, issue_cols], df.loc[stop, 'cf'])],
        categorical_feature=['region'],
        callbacks=[lgb.early_stopping(100, verbose=False)]
    )

if not issue_ev.any():
    raise ValueError('2024년 비교 표본이 없습니다. 날짜와 lag48을 확인하세요.')

df['p_issue14'] = pred(fit_issue(), issue_cols).clip(0, 1)
R['solar_issue_14'] = {
    'issue_kst': '목표일 전날 14:00, 원본 시각을 KST로 가정',
    'features': issue_cols,
    'test_rows': int(issue_ev.sum()),
    'test_dates': int(df.loc[issue_ev, 't'].dt.normalize().nunique()),
    'excluded_no_lag48': int((TE & solar_ok & df.lag48.isna()).sum()),
    'lag48_baseline': metr(df.lag48, issue_ev),
    'lightgbm': metr(df.p_issue14, issue_ev),
    'observed_weather_lag24_reference': metr(df.p_main, issue_ev),
}
```

### ② 시간순으로 분리한 80% 예측구간

**삽입 위치**는 ① 바로 뒤입니다. **저장 키는 `solar_interval_issue_14`**입니다.

2020~2022년으로 학습하고, 2023년 상반기로 조기 종료하고, 하반기로 보정합니다. 2024년 시험 행은 ①과 같습니다. 보정 순위는 `ceil((n+1)×0.8)`을 사용합니다. 이 구현은 음수 보정량을 0으로 제한해 구간을 축소하지 않는 설정입니다. 기존 74.8% → 80.4%는 관측 입력을 쓴 기존 실험의 결과이므로, 새 결과와 비교할 때 입력과 평가 표본이 달라졌음을 표기합니다. [Romano 외, CQR](https://papers.neurips.cc/paper/8613-conformalized-quantile-regression.pdf)

```python
alpha = 0.20
p10 = pred(fit_issue(alpha=0.10), issue_cols).clip(0, 1)
p90 = pred(fit_issue(alpha=0.90), issue_cols).clip(0, 1)
lo = pd.Series(np.minimum(p10, p90), index=df.index)
hi = pd.Series(np.maximum(p10, p90), index=df.index)

cal = VA & df.t.dt.month.ge(7) & solar_ok & df.lag48.notna()
scores = np.maximum(lo - df.cf, df.cf - hi)[cal].to_numpy()
rank = int(np.ceil((len(scores) + 1) * (1 - alpha)))
if rank > len(scores):
    raise ValueError('2023년 하반기 보정 표본이 부족합니다.')

qhat = max(0.0, float(np.partition(scores, rank - 1)[rank - 1]))
df['p10_issue14c'] = (lo - qhat).clip(0, 1)
df['p90_issue14c'] = (hi + qhat).clip(0, 1)

def interval_metrics(lower, upper, mask):
    y = df.loc[mask, 'cf']
    lower, upper = lower[mask], upper[mask]
    width = upper - lower
    penalty = (2 / alpha) * (
        (lower - y).clip(lower=0) + (y - upper).clip(lower=0)
    )
    return {
        'n': int(len(y)),
        'coverage_pct': round(float(100 * y.between(lower, upper).mean()), 2),
        'mean_width_pp': round(float(100 * width.mean()), 2),
        'interval_score_pp': round(float(100 * (width + penalty).mean()), 2),
    }

lower, upper = df.p10_issue14c, df.p90_issue14c
R['solar_interval_issue_14'] = {
    'target_coverage_pct': 80,
    'early_stop': '2023-01~06',
    'calibration': '2023-07~12',
    'n_calibration': int(len(scores)),
    'qhat_cf': qhat,
    'raw_crossings_test': int(((p10 > p90) & issue_ev).sum()),
    'raw_sorted': interval_metrics(lo, hi, issue_ev),
    'calibrated': interval_metrics(lower, upper, issue_ev),
    'by_month': {
        str(month): interval_metrics(lower, upper, issue_ev & df.t.dt.month.eq(month))
        for month in sorted(df.loc[issue_ev, 't'].dt.month.unique())
    },
}
```

### ③ 연료전지 지속 저하 후보 알림

**삽입 위치**는 `R['fuelcell']` 계산 직후, 태양광 인접 비교 앞입니다. **저장 키는 `fuelcell_cusum`**입니다.

발전소별 첫 90달력일 중 유효 관측 60일 이상을 기준으로 삼습니다. 초기 중앙값과 MAD를 고정하고, 이후 이용률 하락을 누적합니다. `k=0.5`, `h=4`와 변동 척도 하한 `0.02`(2%p)는 시범 설정입니다. 척도 하한은 초기 출력이 거의 일정해 MAD가 0에 가까울 때 작은 변화가 과도하게 증폭되는 것을 막습니다. 결측·품질 제외일은 누적을 끊습니다. 기존 급락 알림과는 **양쪽 모두 판정 가능한 같은 날짜**에서 겹침을 셉니다.

```python
def count_starts(flags):
    return int((flags & ~flags.shift(1, fill_value=False)).sum())

R['fuelcell_cusum'] = {
    'baseline_calendar_days': 90, 'min_baseline_obs': 60,
    'allowance_sigma': 0.5, 'threshold': 4.0, 'scale_floor_cf': 0.02,
    'plants': {},
}
for name, g in fcd.groupby('발전설비'):
    daily = (
        g.sort_values('d').set_index('d')[['cf', 'alert', 'z']]
        .asfreq('D')
    )
    cf = daily.cf.where(daily.cf.between(0, 1.05))
    baseline = cf.iloc[:90].dropna()
    monitor = cf.iloc[90:]
    if len(baseline) < 60 or not monitor.notna().any():
        R['fuelcell_cusum']['plants'][name] = {
            'judgeable': False, 'baseline_obs': int(len(baseline))
        }
        continue

    center = float(baseline.median())
    mad = float((baseline - center).abs().median())
    scale = max(1.4826 * mad, 0.02)
    score, values = 0.0, []
    for value in monitor:
        if pd.isna(value):
            score = 0.0
            values.append(np.nan)
            continue
        score = max(0.0, score + (center - value) / scale - 0.5)
        values.append(score)

    slow = pd.Series(values, index=monitor.index).ge(4.0)
    paired = monitor.notna() & np.isfinite(daily.loc[monitor.index, 'z'])
    acute = daily.loc[monitor.index, 'alert'].eq(True) & paired
    starts = slow & ~slow.shift(1, fill_value=False)
    R['fuelcell_cusum']['plants'][name] = {
        'judgeable': True,
        'baseline_obs': int(len(baseline)),
        'baseline_end': str(cf.index[89].date()),
        'baseline_cf': round(center, 4),
        'scale_cf': round(scale, 4),
        'monitored_obs': int(monitor.notna().sum()),
        'missing_or_excluded_days': int(monitor.isna().sum()),
        'cusum_alert_days': int(slow.sum()),
        'cusum_events': count_starts(slow),
        'paired_days': int(paired.sum()),
        'both_alert_days': int((slow & acute).sum()),
        'cusum_only_paired_days': int((slow & paired & ~acute).sum()),
        'event_starts': [str(day.date()) for day in starts.index[starts]],
    }
```

CUSUM은 하락이 누적되면 회복 후에도 점수가 한동안 남을 수 있습니다. `cusum_alert_days`는 임계값 위에 있었던 일수이고, `cusum_events`는 임계값을 새로 넘은 구간 수입니다. 시연에서는 한 설비의 이용률, 초기 기준선, 급락일, CUSUM 시작점을 함께 보여주면 두 규칙의 차이를 설명하기 쉽습니다.

## 4. 하지 말아야 할 것

- **발행 이후의 값을 넣기.** 전날 14시에 다음 날 전체를 예측한다면 `lag24` 일부, 대상일 관측 기상·일사량, LNG의 당일 관측 수요는 사후 입력입니다. LNG의 전날 일합계도 실제 발행 시각에 집계가 끝났는지 확인해야 합니다.
- **공식 예측과의 하루 비교를 운영 모델의 우열로 발표하기.** 첨부 `kpx_day`에는 하루치 표본, 관측 기상 입력, 계량 대상과 설비용량 기준 차이가 함께 들어 있습니다. 이 수치는 입력 조건을 표시한 사례로 제시합니다.
- **시험 결과를 보면서 임계값이나 모델을 고르기.** 2024년 태양광과 2021년 LNG는 최종 평가에 둡니다. CUSUM 기준 초기 구간에 장기 정지나 설비 변경이 있으면 결과 해석에 표시합니다. 중부발전 전 기간 최대 설비용량 보정이 과거에 알 수 있었던 설비용량과 일치하는지도 **확인 필요**입니다.
- **결측과 실제 0을 합치기.** 풍력·소수력의 결측일은 연속 구간을 끊습니다. LNG에서는 `L_missing`이 두 열의 결측 건수를 더해 같은 날짜를 중복 집계할 수 있습니다. 누락 날짜는 행 단위로 세고, 시간별 수요 합산은 `sum(axis=1, min_count=24)`로 불완전한 하루를 드러낸 뒤 평가 제외 건수를 확인합니다.
- **3일 안에 대형 모델이나 전체 기상예보 수집부터 시작하기.** 현재 일정에서는 공통 시험 표본, 발행 시각, 결측 처리 검증이 발표 해석에 직접 영향을 줍니다. 이상 후보 수를 고장 수나 검출 정확도로 발표하는 것도 정비 기록이 확보될 때까지 보류합니다.

## 5. 참고문헌

1. IEA PVPS Task 16. *Best Practices Handbook for the Collection and Use of Solar Resource Data for Solar Energy Applications*, 4판, 9장. [공식 PDF](https://iea-pvps.org/wp-content/uploads/2024/09/Best-Practices-Handbook-for-the-Collection-and-Use-of-Solar-Resource-Data-for-Solar-Energy-Applications-Fourth-Edition-.pdf)
2. Koster 외. *Single-Site Forecasts for 130 Photovoltaic Systems at Distribution System Operator Level, Using a Hybrid-Physical Approach*. [Solar RRL](https://doi.org/10.1002/solr.202200652)
3. Romano, Patterson, Candès. *Conformalized Quantile Regression*. [NeurIPS 원문 PDF](https://papers.neurips.cc/paper/8613-conformalized-quantile-regression.pdf)
4. Gneiting, Raftery. *Strictly Proper Scoring Rules, Prediction, and Estimation*. [논문 PDF](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf)
5. Xu, Xie. *Conformal Prediction Interval for Dynamic Time-Series*. [ICML 논문](https://proceedings.mlr.press/v139/xu21h.html)
6. NIST/SEMATECH. *e-Handbook of Statistical Methods*. [CUSUM 평균 신호 길이](https://itl.nist.gov/div898/handbook/pmc/section3/pmc3231.htm), [EWMA 관리도](https://itl.nist.gov/div898/handbook/mpc/section2/mpc2211.htm)
7. IEA PVPS Task 13. *Guidelines for Operation and Maintenance of PV Power Plants in Different Climates*. [공식 보고서 PDF](https://pvpmc.sandia.gov/app/uploads/sites/243/dlm_uploads/2022/12/IEA-PVPS-Report-T13-25-2022-OandM-Guidelines.pdf)
8. Fan, Hyndman. *GEFCom2014 Probabilistic Electric Load Forecasting Using Time Series and Semi-Parametric Regression Models*. [International Journal of Forecasting](https://doi.org/10.1016/j.ijforecast.2015.11.010)
9. Hyndman, Athanasopoulos. *Forecasting: Principles and Practice*, 3판. [예측 기준선과 시간순 교차검증](https://otexts.com/fpp3/toolbox.html)
10. U.S. EIA. *Electricity Market Module of the National Energy Modeling System*, 2025. [급전 모형 문서](https://www.eia.gov/outlooks/aeo/nems/documentation/electricity/pdf/EMM_AEO2025.pdf)
11. 기상청. [API허브 단기예보 문서](https://apihub.kma.go.kr/apiList.do?seqApi=10), [동네예보 격자자료 조회 안내](https://apihub.kma.go.kr/notice.do?seqNotice=21)