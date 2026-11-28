"""기상청 지상관측(ASOS) 시간자료를 지점별로 받아 월별 CSV에 저장한다.

실행: KMA_KEY=<인증키> python fetch_kma.py 2025
"""
import csv
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from http.client import HTTPException
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlencode

OUT = Path('data/kma')
API_URL = 'https://apihub.kma.go.kr/api/typ01/url/kma_sfctm3.php'
COLS = {0: 'tm', 1: 'stn', 3: 'ws', 11: 'ta', 13: 'hm', 15: 'rn', 25: 'ca_tot', 33: 'ss', 34: 'si'}
MAX_RETRIES = 6


def fetch_station(key, station, start, end):
    params = urlencode({
        'tm1': start, 'tm2': end, 'stn': station, 'help': 0, 'authKey': key,
    })
    for attempt in range(MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(f'{API_URL}?{params}', timeout=60) as response:
                body = response.read().decode('cp949')
            if '#START7777' not in body:
                raise ValueError
            rows = []
            for line in body.splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                fields = line.split()
                rows.append(tuple(fields[index] for index in COLS))
            return rows
        except (OSError, HTTPException, ValueError, IndexError):
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)

    print(f'조회 실패 (지점 {station}, {start}~{end})', file=sys.stderr, flush=True)
    return None


def write_month(path, rows):
    with NamedTemporaryFile(
        mode='w', encoding='utf-8', newline='', dir=path.parent, delete=False,
    ) as output:
        temporary_path = Path(output.name)
        try:
            writer = csv.writer(output, lineterminator='\n')
            writer.writerow(COLS.values())
            writer.writerows(rows)
            output.close()
            temporary_path.replace(path)
        finally:
            temporary_path.unlink(missing_ok=True)


def main():
    key = os.environ.get('KMA_KEY')
    if not key:
        sys.exit('환경변수 KMA_KEY를 설정하세요.')
    year = int(sys.argv[1])
    with (OUT / 'stations.txt').open(encoding='utf-8') as station_file:
        stations = [
            line.split()[0] for line in map(str.strip, station_file)
            if line and not line.startswith('#')
        ]

    failed = False
    with ThreadPoolExecutor(max_workers=4) as executor:
        for month in range(1, 13):
            path = OUT / f'asos_{year:04d}{month:02d}.csv'
            if path.exists():
                continue
            first = date(year, month, 1)
            next_month = date(year + month // 12, month % 12 + 1, 1)
            start = f'{first:%Y%m%d}0100'
            end = f'{next_month:%Y%m%d}0000'
            results = list(executor.map(
                lambda station: fetch_station(key, station, start, end), stations,
            ))
            if any(result is None for result in results):
                failed = True
                continue
            rows = [row for result in results for row in result]
            rows.sort(key=lambda row: (row[0], int(row[1])))
            write_month(path, rows)
            print(path, len(rows), '행', flush=True)
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())
