"""공공데이터포털(data.go.kr)에서 원 데이터를 내려받아 data/ 에 UTF-8로 저장한다.
실행: python fetch_data.py   (기본 9종, 로그인 불필요, 약 1분)
      python fetch_data.py --public   (추가 41종 → data/public/, analyze_public.py·2·3용, 약 320MB. 기본 9종과 합쳐 50종)
- supply_daily_2025.csv 는 포털에 파일이 없고 전력거래소 EPSIS 링크만 있어 받지 않는다(analyze.py가 이전 값을 유지).
- 포털 파일은 기관이 갱신하면 내용이 바뀔 수 있다. 2026-11-28에 받은 파일로 기존 결과가 그대로 재현됨을 확인했다.
"""
import io, json, os, re, time, urllib.parse, urllib.request, zipfile

BASE = 'https://www.data.go.kr'
FILES = {  # 저장 이름: (공공데이터포털 번호, 데이터 이름)
    'solar_hourly_sido_2020_2024.csv': (15151005, '한국동서발전_전국 태양광 발전량 예측값 학습데이터'),
    'kpx_solar_forecast_20241202.csv': (15151010, '한국동서발전_전국 태양광 발전량 예측값(2024-12-02)'),
    'komipo_plants_daily_2023_2026.csv': (15004239, '한국중부발전_신재생에너지 발전량'),
    'fuel_daily_region_2018_2022.csv': (15069345, '한국전력거래소_일별 화력발전량'),
    'demand_hourly_2017_2021.csv': (15065387, '한국전력거래소_시간별 발전량(2017~2021)'),
    'thermal_units_daily_2022_2023.csv': (15123066, '한국서부발전_발전소별 발전량(태안)'),
    'nuclear_annual_cf_2014_2025.csv': (15002302, '한국수력원자력_원자력발전소 호기별 발전량 및 이용률'),
    'nuclear_annual_gen_2019_2025.csv': (15046077, '원자력안전위원회_국내원전 호기별 발전량'),
    'nuclear_units_2025.csv': (15046076, '원자력안전위원회_국내 원자력발전소 현황'),
}

PUBLIC = {  # 추가 자료(analyze_public.py): 원본 그대로 data/public/<번호>.csv|zip 로 저장
    15126707: '한국수목원정원관리원_국립세종수목원 지열 이용량', 15157241: '기후에너지환경부_신재생에너지 생산량',
    15149953: '한국지역난방공사_연도별 공급자별 외부 수열량', 15123991: '한국지역난방공사_시간대별 수열량 정보',
    15150813: '한국동서발전_바이오매스 연료분석결과',
    15114951: '한국수력원자력_원전 호기별 계획예방정비 현황', 15060801: '한국수력원자력_가동원전 호기별 계획예방정비 계획',
    15074543: '한국원자력안전기술원_연도별 원전 사고고장 현황', 15061937: '한국수력원자력_보고대상사건 현황',
    15069337: '한국전력거래소_신재생 발전량 및 설비용량',
    15132422: '한국전력거래소_전국 태양광 풍력 제어횟수 및 제주 풍력 제어량',
    15152008: '한국전력거래소_육지 제주 통합 월별 계통한계가격', 15153657: '한국전력거래소_연료원별 일별 설비용량',
    15086290: '한국에너지공단_신재생에너지 연도별 신규보급 현황', 15140231: '한국중부발전_발전소별 예방정비실적 정보',
    15136947: '한국서부발전_설비 신뢰성 데이터',
    # 2차(GPT 조사 추천, analyze_public2.py)
    15159034: '한국서부발전_(AI친화)장흥풍력발전소 스카다 발전 정보', 15159036: '한국서부발전_(AI친화)화순풍력발전소 스카다 발전 정보',
    15043410: '한국남부발전_한경풍력발전실적', 15028181: '제주에너지공사_풍력발전기 전력 정보',
    15165984: '한국수력원자력_(AI친화고가치)기상정보를 융합한 한수원 태양광 시계열 발전정보', 15083316: '한국동서발전_(발전공기업 표준) 발전실적 정보',
    15095396: '한국남부발전_연료전지 발전실적', 15118844: '충청남도개발공사_에너지 사용현황',
    15164288: '한국지역난방공사_외기온도에 따른 전체 열생산량 대비 타사 수열량 데이터', 15161308: '한국전력거래소_제주발전기 연료원 시간대별 전력거래량',
    15121931: '한국수자원공사_소수력 잠재 발전 가능량 데이터', 15149686: '경기도 부천시_공공하수처리시설 바이오가스 자체활용 현황',
    15131797: '한국지역난방공사_플랜트관리 예방정비 관리 실적',
    # 3차(GPT 조사 추천, analyze_public3.py)
    15106338: '한국서부발전_일별 발전실적 정보', 15106292: '한국서부발전_풍력 발전 현황', 15076400: '한국남부발전_성산풍력 일평균 풍속데이터',
    15167614: '한국남동발전_시간대별 태양광 실적 및 메타데이터', 15041895: '한국수력원자력_수력양수 발전량 및 이용률',
    15099592: '한국서부발전_대기오염물질 배출현황 및 발전량', 15074207: '한국남부발전_온실가스 배출량 정보',
    15155623: '한국중부발전_발전소별 발전연료 입출고 및 재고 현황', 15144100: '한국남동발전_온배수 수온 현황',
    15161908: '한국전력거래소_육지 및 제주 계통한계가격(SMP) 결정 발전기 연료원', 15065266: '한국전력거래소_시간별 전국 전력수요량',
    15151942: '광주환경공단_1하수관리처_혐기성 소화조 운영 데이터',
}

def get(url, data=None, tries=5):
    for i in range(tries):                                # 포털이 연결을 가끔 끊어서 다시 시도
        try:
            req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode() if data else None,
                                         headers={'User-Agent': 'Mozilla/5.0'})
            return urllib.request.urlopen(req, timeout=600).read()
        except OSError as e:
            if i == tries - 1: raise
            print(f'  재시도 {i + 1}/{tries - 1}: {e}'); time.sleep(3 * (i + 1))

def download(pk):
    page = get(f'{BASE}/data/{pk}/fileData.do').decode('utf-8', 'replace')
    m = re.search(r"fn_fileDataDown\('(\d+)',\s*'([^']+)',\s*'([^']*)',\s*'(\d+)',\s*'(\d+)'\)", page)
    if not m: raise RuntimeError(f'{pk}: 다운로드 버튼을 찾지 못함')
    _, dpk, atch, sn, _ = m.groups()
    j = json.loads(get(f'{BASE}/tcs/dss/selectFileDataDownload.do',
                       dict(publicDataDetailPk=dpk, publicDataPk=pk, atchFileId=atch, fileDetailSn=sn, publicDataTyCode='PR0051')))
    nm = j['dataSetFileDetailInfo']['dataNm']
    return get(f"{BASE}/cmm/cmm/fileDownload.do?atchFileId={j['atchFileId']}&fileDetailSn={j['fileDetailSn']}&dataNm={urllib.parse.quote(nm)}")

def to_text(b):
    if b[:2] == b'PK':                                   # zip이면 첫 번째 csv
        z = zipfile.ZipFile(io.BytesIO(b)); b = z.read([n for n in z.namelist() if n.lower().endswith('.csv')][0])
    for enc in ('utf-8-sig', 'cp949'):
        try: return b.decode(enc)
        except UnicodeDecodeError: pass
    raise RuntimeError('인코딩을 알 수 없음')

if __name__ == '__main__':
    import sys
    if '--public' in sys.argv:                           # python fetch_data.py --public
        os.makedirs('data/public', exist_ok=True)
        for pk, name in PUBLIC.items():
            b = download(pk); ext = 'zip' if b[:2] == b'PK' else 'csv'
            open(f'data/public/{pk}.{ext}', 'wb').write(b); print(f'{pk}.{ext:4s} ← {name} ({len(b):,} bytes)')
        sys.exit()
    os.makedirs('data', exist_ok=True)
    for out, (pk, name) in FILES.items():
        t = to_text(download(pk))
        open(os.path.join('data', out), 'w', encoding='utf-8', newline='').write(t)
        print(f'{out:38s} ← {pk} {name} ({t.count(chr(10)):,}줄)')
