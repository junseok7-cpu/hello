"""전날 14시 기상청 단기예보를 사용한 2025년 11월 2주 표본 실험."""
import gzip
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd

import analyze_plan as plan

NX, NY = 149, 253
FCST = Path('data/kma/fcst')
VARIABLES = {'SKY': 'ca_tot', 'TMP': 'ta', 'WSD': 'ws', 'REH': 'hm'}
CITIES = {
    '서울': (108, 60, 127),
    '부산': (159, 98, 76),
    '제주': (184, 52, 38),
}
LABELS = {'no_weather': '날씨 없음', 'observed': '관측 날씨', 'forecast': '실제 예보'}


def station_grid(lon, lat):
    # 기상청 동네예보 LCC. 투영 좌표를 가장 가까운 정수 격자로 반올림한다.
    re = 6371.00877 / 5.0
    slat1, slat2, olon, olat = np.deg2rad([30, 60, 126, 38])
    t1 = np.tan(np.pi / 4 + slat1 / 2)
    t2 = np.tan(np.pi / 4 + slat2 / 2)
    sn = np.log(np.cos(slat1) / np.cos(slat2)) / np.log(t2 / t1)
    sf = t1 ** sn * np.cos(slat1) / sn
    ro = re * sf / np.tan(np.pi / 4 + olat / 2) ** sn
    ra = re * sf / np.tan(np.pi / 4 + np.deg2rad(lat) / 2) ** sn
    theta = (np.deg2rad(lon) - olon + np.pi) % (2 * np.pi) - np.pi
    nx = np.floor(ra * np.sin(theta * sn) + 43 + 0.5).astype(int)
    ny = np.floor(ro - ra * np.cos(theta * sn) + 136 + 0.5).astype(int)
    return nx, ny


def read_grid(path):
    with gzip.open(path, 'rt', encoding='ascii') as source:
        # 줄마다 쉼표로 끝나며, 빈 줄은 격자 위치에 영향을 주지 않는다.
        values = np.asarray(source.read().strip().rstrip(',').split(','), dtype=float)
    if values.size != NX * NY:
        raise ValueError(f'{path}: 격자 값 {values.size}개, 기대값 {NX * NY}개')
    values[values <= -99] = np.nan
    return values


def forecast_weather(hours):
    stations = pd.read_csv(io.StringIO(plan.text(Path('data/kma/stations.txt').read_bytes())),
                           sep=r'\s+', comment='#', header=None, usecols=[0, 1, 2],
                           names=['stn', 'lon', 'lat'])
    stations['nx'], stations['ny'] = station_grid(stations.lon, stations.lat)
    stations['region'] = stations.stn.map(plan.regions)
    stations = stations[stations.nx.between(1, NX) & stations.ny.between(1, NY)]
    indices = (stations.ny - 1) * NX + stations.nx - 1
    records, checks, missing = [], [], []
    for hour in hours:
        issued = hour.normalize() - pd.Timedelta(hours=10)
        row = stations[['region']].assign(t=hour)
        for var, column in VARIABLES.items():
            path = FCST / f'{var}_{issued:%Y%m%d%H}_{hour:%Y%m%d%H}.txt.gz'
            try:
                grid = read_grid(path)
            except FileNotFoundError:
                missing.append(path.name)
                row[column] = np.nan
                continue
            row[column] = grid[indices]
            if var == 'TMP':
                for city, (stn, nx, ny) in CITIES.items():
                    checks.append((hour, city, stn, grid[(ny - 1) * NX + nx - 1],
                                   grid[(nx - 1) * NY + ny - 1]))
        records.append(row)
    records = pd.concat(records, ignore_index=True)
    # ASOS 운량은 하늘을 덮은 비율의 10분율이다. SKY 세 범주를
    # 맑음 0, 구름많음 6, 흐림 10의 대표값으로 근사한다.
    records['ca_tot'] = records.ca_tot.map({1: 0, 3: 6, 4: 10})
    return plan.aggregate_weather(records, ['ca_tot', 'ta']), checks, missing


def validate_grid(checks):
    # 지정 검증 격자에서 같은 시각 ASOS와 비교한 TMP MAE(166쌍)는
    # 서울 1.27, 부산 1.79, 제주 0.94°C로 ny 바깥 순서를 지지한다.
    # nx 바깥으로 읽으면 서울·제주는 전부 결측이고 부산은 7.71°C다.
    check = pd.DataFrame(checks, columns=['t', 'city', 'stn', 'ny_outer', 'nx_outer'])
    check = check.merge(plan.weather[['t', 'stn', 'ta']], on=['t', 'stn'], validate='one_to_one')
    result = {}
    for city, group in check.groupby('city'):
        _, nx, ny = CITIES[city]
        stats = {}
        for order in ['ny_outer', 'nx_outer']:
            error = (group[order] - group.ta).dropna()
            stats[order] = {'pairs': len(error), 'MAE_C': round(float(error.abs().mean()), 2) if len(error) else None}
        result[city] = {'nx': nx, 'ny': ny, **stats}
    return result


def evaluate(hours, forecast):
    sample = plan.df.loc[hours]
    predictions = {label: pd.DataFrame(index=hours) for label in LABELS}
    month = hours[0].normalize().replace(day=1)
    for target, base in plan.FE.items():
        weather = [col for col in plan.WEATHER_FE[target] if col in forecast.columns]
        columns = base + weather
        baseline = plan.fit_model(target, base, month, n_jobs=2)
        model = plan.fit_model(target, columns, month, n_jobs=2)
        predictions['no_weather'][target] = plan.predict_model(baseline, sample[base], target)
        predictions['observed'][target] = plan.predict_model(model, sample[columns], target)
        inputs = sample[base].join(forecast[weather])
        predictions['forecast'][target] = plan.predict_model(model, inputs[columns], target)

    valid = (sample[['demand', 'solar', 'wind', 'net']].notna().all(axis=1)
             & (sample[['demand', 'solar_cap', 'wind_cap']] > 0).all(axis=1))
    for prediction in predictions.values():
        valid &= prediction.notna().all(axis=1)
    sample = sample.loc[valid]
    metrics = {}
    for label, prediction in predictions.items():
        prediction = prediction.loc[valid]
        net = prediction.demand - prediction.solar - prediction.wind
        scores = {
            'demand_MAPE_pct': plan.errs(sample.demand, prediction.demand)['MAPE_pct'],
            'net_reserve_P95_MW': plan.errs(sample.net, net)['reserve_P95_MW'],
        }
        for source in ['solar', 'wind']:
            error = (sample[source] - prediction[source]).abs()
            scores[f'{source}_nMAE_pct'] = round(float((error / sample[f'{source}_cap']).mean() * 100), 2)
        metrics[label] = scores
    return metrics, len(sample)


def draw(metrics):
    fig, ax = plan.plt.subplots(figsize=(10, 3.4))
    x = np.arange(2)
    for i, (key, label) in enumerate(LABELS.items()):
        values = [metrics[key][f'{source}_nMAE_pct'] for source in ['solar', 'wind']]
        bars = ax.bar(x + (i - 1) * .24, values, width=.22,
                      color=[plan.MUTED, plan.NUC, plan.MAIN][i], label=label)
        ax.bar_label(bars, fmt='%.2f', padding=3)
    ax.set_xticks(x, ['태양광', '풍력'])
    ax.set_ylabel('설비용량 대비 평균 절대 오차 (%)')
    ax.set_ylim(0, ax.get_ylim()[1] * 1.3)
    ax.legend(frameon=False, ncol=3, loc='upper center')
    ax.set_title('2025년 11월 17~30일 07~18시 (2주 표본)', loc='left')
    plan.save('f30_plan_forecast.png')


def main():
    hours = pd.date_range('2025-11-17 07:00', '2025-11-30 18:00', freq='h')
    hours = hours[hours.hour.isin(range(7, 19))]
    # tmef는 KST 예보 대상 시각이다. 관측 입력은 기존 관측-발전 정렬을 유지한다.
    forecast, checks, missing = forecast_weather(hours)
    grid_check = validate_grid(checks)
    metrics, count = evaluate(hours, forecast)
    result = {
        'period_test': '2025-11-17~2025-11-30, 07~18시 KST',
        'sample_weeks': 2,
        'target_hours': len(hours),
        'test_hours': count,
        'missing_file_count': len(missing),
        'missing_files': missing,
        'missing_policy': '누락된 예보 항목은 NaN으로 유지하여 LightGBM이 처리',
        'alignment': {'observed_shift_hours': plan.weather_shift, 'forecast_tmef_shift_hours': 0},
        'conditions': metrics,
        'grid_validation': {'order': 'ny 바깥, nx 안쪽', 'same_time_TMP_vs_ASOS': grid_check},
        'caution': '11월 낮 시간 2주 표본이라 참고값이다.',
    }
    draw(metrics)
    plan.R['plan']['forecast_sample'] = result
    # 기존 결과 파일의 들여쓰기와 키 순서를 유지한다.
    Path(plan.RJ).write_text(json.dumps(plan.R, ensure_ascii=False, indent=1, allow_nan=False), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
