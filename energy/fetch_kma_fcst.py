"""기상청 단기예보 격자자료(nph-dfs_shrt_grd) 표본 받기: 전날 14시 발표 → 다음날 낮 시간
실행: KMA_KEY=<키> python fetch_kma_fcst.py 2025-11-17 2025-11-30
저장: data/kma/fcst/<변수>_<발표시각>_<예보시각>.txt.gz (전국 격자 원문, 쉼표 구분 37,697개 값)"""
import os, sys, gzip, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
KEY = os.environ['KMA_KEY']; OUT = 'data/kma/fcst/'
VARS, HOURS = ['SKY', 'TMP', 'WSD', 'REH'], range(7, 19)
jobs = []
for d in pd.date_range(sys.argv[1], sys.argv[2]):
    tmfc = (d - pd.Timedelta(days=1)).strftime('%Y%m%d') + '14'
    for h in HOURS:
        for v in VARS: jobs.append((v, tmfc, d.strftime('%Y%m%d') + f'{h:02d}'))
def get(j):
    v, tmfc, tmef = j; f = f'{OUT}{v}_{tmfc}_{tmef}.txt.gz'
    if os.path.exists(f): return 1
    url = f'https://apihub.kma.go.kr/api/typ01/cgi-bin/url/nph-dfs_shrt_grd?tmfc={tmfc}&tmef={tmef}&vars={v}&authKey={KEY}'
    for i in range(5):
        try:
            b = urllib.request.urlopen(url, timeout=240).read()
            if b.count(b',') > 30000: gzip.open(f, 'wb').write(b); return 1
        except Exception: pass
        time.sleep(5 * (i + 1))
    print('실패', v, tmfc, tmef, flush=True); return 0
with ThreadPoolExecutor(8) as ex: ok = sum(ex.map(get, jobs))
print('완료', ok, '/', len(jobs))
