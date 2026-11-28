"""기상청 API허브 지상관측(ASOS) 시간자료를 한 시각씩 받아 data/kma/asos_YYYYMM.csv 로 저장한다.
실행: KMA_KEY=<인증키> python fetch_kma.py 2025      (인증키는 파일에 저장하지 않는다)
사용 API: kma_sfctm2.php (한 시각 전 지점 조회). 받는 열: 시각, 지점, 풍속, 기온, 습도, 강수, 전운량, 일조, 일사
"""
import os, sys, time, io, csv, urllib.request
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
KEY = os.environ['KMA_KEY']; YEAR = int(sys.argv[1]); OUT = 'data/kma/'
COLS = {0: 'tm', 1: 'stn', 3: 'ws', 11: 'ta', 13: 'hm', 15: 'rn', 25: 'ca_tot', 33: 'ss', 34: 'si'}
def get(tm):
    url = f'https://apihub.kma.go.kr/api/typ01/url/kma_sfctm2.php?tm={tm}&stn=0&help=0&authKey={KEY}'
    for i in range(6):
        try:
            t = urllib.request.urlopen(url, timeout=60).read().decode('cp949', 'replace')
            if '#START7777' not in t: raise RuntimeError(t[:80])
            rows = [l.split() for l in t.splitlines() if l and not l.startswith('#')]
            return [{v: r[k] for k, v in COLS.items() if k < len(r)} for r in rows if len(r) > 35]
        except Exception as e:
            time.sleep(2 * (i + 1)); err = e
    print('실패', tm, err, flush=True); return []
os.makedirs(OUT, exist_ok=True)
for m in range(1, 13):
    f = f'{OUT}asos_{YEAR}{m:02d}.csv'
    if os.path.exists(f): continue
    hours = pd.date_range(f'{YEAR}-{m:02d}-01 01:00', periods=pd.Period(f'{YEAR}-{m:02d}').days_in_month * 24, freq='h')
    with ThreadPoolExecutor(6) as ex: res = list(ex.map(lambda t: get(t.strftime('%Y%m%d%H00')), hours))
    df = pd.DataFrame([r for rr in res for r in rr])
    df.to_csv(f, index=False); print(f, len(df), '행', flush=True)
