// 최종보고서 생성: node report.js <energy 폴더>
const fs = require('fs'), path = require('path');
const { Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, ShadingType,
  AlignmentType, ImageRun, PageBreak, LevelFormat, Footer, PageNumber, TableOfContents, BorderStyle } = require('docx');

const E = process.argv[2];
const R = JSON.parse(fs.readFileSync(path.join(E, 'results/results.json'), 'utf8'));
const AU = JSON.parse(fs.readFileSync(path.join(E, 'results/data_audit.json'), 'utf8'));
const FONT = 'Malgun Gothic', TEAL = '0F6E6A', INK = '1D2B36', GRID = 'C9D3D8', HEAD = 'E3EFEE';
const f1 = (x) => Number(x).toFixed(1), f2 = (x) => Number(x).toFixed(2), pct = (x) => (x * 100).toFixed(1);
const A = R.A, B = R.B, C = R.C, Dd = R.D, IV = R.interval, KD = R.kpx_day, FO = R.follow, NU = R.nuclear, SP = R.supply2025;
const B1k = Object.keys(B)[1];
const LP = R.lng_pred, WHd = R.wind_hydro, SI = R.solar_issue_14, SII = R.solar_interval_issue_14, CU = R.fuelcell_cusum;
const P1 = R.public, P2 = R.public2, P3 = R.public3;
const CAT = JSON.parse(fs.readFileSync(path.join(E, 'report/catalog.json'), 'utf8'));
const LM = LP.models, kR = '선형회귀 · 전날 수요만 입력(현실 조건)', kU = '선형회귀 · 관측 수요 입력(사후 참고)', kN = '선형회귀 · 수요 없음(달력+과거 LNG)', kP = '어제 값(Persistence)';

const t = (text, o = {}) => new TextRun({ text, font: FONT, ...o });
const P = (runs, o = {}) => new Paragraph({ children: (typeof runs === 'string' ? [t(runs)] : runs), spacing: { after: 120, line: 320 }, ...o });
const H1 = (s) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [t(s)] });
const H2 = (s) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [t(s)] });
const BL = (runs) => new Paragraph({ numbering: { reference: 'bul', level: 0 }, children: (typeof runs === 'string' ? [t(runs)] : runs), spacing: { after: 80, line: 300 } });
const b = (s) => t(s, { bold: true });
const NOTE = (s) => new Paragraph({ children: [t(s, { size: 18, color: '5A6670' })], spacing: { after: 160 } });

const W = 9026; // A4 본문 폭(DXA, 여백 1in)
function table(head, rows, widths) {
  const sum = widths.reduce((a, c) => a + c, 0); widths = widths.map(w => Math.round(w / sum * W));
  widths[widths.length - 1] += W - widths.reduce((a, c) => a + c, 0);
  const border = { style: BorderStyle.SINGLE, size: 4, color: GRID };
  const borders = { top: border, bottom: border, left: border, right: border };
  const cell = (s, i, h) => new TableCell({ width: { size: widths[i], type: WidthType.DXA }, borders,
    shading: h ? { type: ShadingType.CLEAR, color: 'auto', fill: HEAD } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ children: [t(String(s), { bold: !!h, size: 19 })] })] });
  return new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: widths,
    rows: [new TableRow({ tableHeader: true, children: head.map((s, i) => cell(s, i, true)) }),
           ...rows.map(r => new TableRow({ children: r.map((s, i) => cell(s, i, false)) }))] });
}
let tn = 0, fn = 0;
const TCAP = (s) => new Paragraph({ children: [t(`표 ${++tn}. ${s}`, { bold: true, size: 19 })], spacing: { before: 200, after: 80 }, keepNext: true });
function FIG(file, cap, wIn = 6.2) {
  const p = path.join(E, 'figures', file), buf = fs.readFileSync(p);
  const w = buf.readUInt32BE(16), h = buf.readUInt32BE(20), px = wIn * 96;
  return [new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 120 },
      children: [new ImageRun({ type: 'png', data: buf, transformation: { width: px, height: Math.round(px * h / w) },
        altText: { title: cap, description: cap, name: file } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, children: [t(`그림 ${++fn}. ${cap}`, { size: 18, color: '5A6670' })], spacing: { after: 200 } })];
}

const solarAud = AU.solar_hourly;
const body = [];
const push = (...x) => x.flat().forEach(e => body.push(e));

// ── 표지
push(
  new Paragraph({ spacing: { before: 2400 }, children: [t('인공지능과 디지털 사고 · 팀 프로젝트 최종보고서', { size: 22, color: TEAL, bold: true })] }),
  new Paragraph({ spacing: { before: 240, after: 120 }, children: [t('발전원별 AI 예측·관리 시스템', { size: 52, bold: true, color: INK })] }),
  new Paragraph({ spacing: { after: 600 }, children: [t('— 수요에 맞춘 발전 계획과 발전원별 예측·이상 후보 알림 —', { size: 28, color: '3C4A55' })] }),
  P([t('제출일: 2026년 12월 1일', { size: 22 })]),
  P([t('팀명: ____________    팀원: ____________ / ____________ / ____________ / ____________', { size: 22 })]),
  new Paragraph({ children: [new PageBreak()] }),
);

// ── 초록
push(H1('초록'),
  P(`발전 설비의 변환 효율은 열역학·공기역학·반도체 물성이 정한 상한에 가까워졌지만, 전력 계통의 실제 과제는 "언제, 얼마나 나올지 모른다"는 출력의 불확실성으로 옮겨 가고 있다. 본 과제는 발전원마다 AI가 풀어야 할 문제가 다르다는 점에서 출발해, 변동성 전원(태양광)은 발전량 예측, 급전 전원(화력)은 수요 추종 분석, 출력이 일정한 기저형 전원(연료전지·원자력)은 이상탐지로 문제를 나누어 설계하였다.`),
  P(`공공데이터 10종을 수집·점검하여 중복 행, 단위 오류, 열 이름 어긋남 등 7건의 데이터 문제를 찾아 보정하였다. 17개 시도의 2020~2024년 시간별 태양광 데이터로 하루 전(day-ahead) 예측 모델을 학습한 결과, LightGBM은 2024년 낮 시간 기준 설비용량 대비 오차(nRMSE) ${f1(A.LightGBM.nRMSE)}%로, "어제 같은 시각과 같다"고 보는 기준선(${f1(A.Persistence.nRMSE)}%)보다 오차를 ${pct(A.LightGBM.Skill)}% 줄였다(Skill Score ${f2(A.LightGBM.Skill)}). 발전량을 설비용량으로 나눈 이용률로 학습하면 예측의 평균 치우침이 ${f1(Dd['원시 발전량(MWh) 학습'].bias)}%p에서 +${f1(Dd['이용률(CF) 학습'].bias)}%p로 줄었고, 분위수 회귀와 2023년 자료로 폭을 조정하는 보정(conformal)을 거친 P10~P90 범위에 2024년 실제값의 ${pct(IV.calibrated_coverage)}%가 들어왔다.`),
  P(`다만 본 실험의 기상 입력은 예보가 아닌 그 시각의 관측값이다. 실제 기상 예보를 넣은 운영 성능은 측정하지 않았으며, 이 점을 한계로 명시하였다.`),
  P(`이어서 공공데이터포털 자료를 50종까지 넓혀 설계의 근거를 확인하였다. 2025년 실적에서 "어제 값"으로 예측할 때의 오차는 연료전지 ${f1(P1.renewables_2025.by_source['연료전지'].dayahead_persistence_nRMSE)}%, 풍력 ${f1(P1.renewables_2025.by_source['풍력'].dayahead_persistence_nRMSE)}%로 달라, 출력을 누가 정하느냐에 따라 AI의 역할이 달라져야 함을 보였다. 실제 운영에 가까운 조건(전날 14시 발행, 관측 기상 미사용)에서 태양광 오차는 ${f1(SI.lightgbm.nRMSE)}%로 관측 기상 결과와의 차이를 수치로 제시했고, 한수원 태양광 ${P2.khnp_solar.plants}곳에서도 같은 결론을 얻었다. LNG 일별 예측은 전날까지의 정보로 어제 값 대비 오차를 ${pct(LM[kR].Skill)}% 줄였고, 원전은 계획예방정비 일수와 연간 이용률의 상관이 ${P1.nuclear_outage.corr_outage_days_vs_cf}로, 원전에서 AI의 몫이 출력 예측이 아니라 정비 관리임을 확인하였다.`),
  P([b('주제어: '), t('발전량 예측, 태양광, 풍력, 이용률 정규화, LightGBM, 예측구간, 이상 후보 알림, 공공데이터, 데이터 품질')]),
  new Paragraph({ children: [new PageBreak()] }),
  H1('목차'),
  new TableOfContents('목차', { hyperlink: true, headingStyleRange: '1-2' }),
  NOTE('※ Word에서 목차가 비어 보이면 목차를 오른쪽 클릭 → "필드 업데이트"를 누르세요.'),
  new Paragraph({ children: [new PageBreak()] }),
);

// ── 1. 서론
push(H1('1. 서론'), H2('1.1 배경'),
  P(`재생에너지 설비가 빠르게 늘고 있다. 본 과제가 사용한 계량 태양광 데이터만 보아도 17개 시도의 설비용량 합계가 2020년 ${f1(Dd.cap_total[0] / 1000)}GW에서 2024년 ${f1(Dd.cap_total[4] / 1000)}GW로 4년 만에 두 배 넘게 늘었다. 태양광과 풍력은 사람이 출력을 정할 수 없고 일사량·풍속이 출력을 정한다. 따라서 전력 운영은 "수요 예측"만이 아니라 "공급 예측"까지 해야 하는 문제로 바뀌고 있다.`),
  P([t('더 중요한 사실은 계통 운영자가 '), b('모든 태양광을 직접 보지는 못한다'), t(`는 점이다. 2024년 12월 1일 발표된 공식 태양광 예측 자료에서 전국 태양광 설비 ${f1(R.metered.total / 1000)}GW 가운데 계량 집계분은 ${f1(R.metered.metered / 1000)}GW(${f1(R.metered.share)}%)였고, 전력구매계약(PPA) ${f1(R.metered.ppa / 1000)}GW와 자가소비(소비자발전) ${f1(R.metered.btm / 1000)}GW는 이 자료에서 추정치로 제공된다. 계량 집계 범위 밖의 설비가 많을수록 예측의 역할이 크다.`)]),
  H2('1.2 문제 정의'),
  P('발전 설비마다 물리 법칙이 정한 효율 상한이 있다(3장). 본 과제는 설비를 "더 잘 만드는 것"과 함께 이미 있는 설비를 "더 잘 아는 것"에 주목해, 다음 질문에 답한다.'),
  BL('공개 데이터만으로 하루 전 태양광 발전량을 얼마나 정확히 예측할 수 있는가?'),
  BL('설비가 계속 늘어나는 상황에서 모델이 날씨가 아니라 "증설 추세"를 배우지 않게 하려면 어떻게 해야 하는가?'),
  BL('예측이 의미 없는 전원(출력이 일정한 기저형 전원)에는 AI를 어떻게 쓸 수 있는가?'),
  H2('1.3 범위'),
  P('구현과 실험은 데이터가 가장 풍부한 태양광 예측에 집중하고, 연료전지·풍력·소수력 이상 후보 알림과 화력의 수요 추종 분석·일별 예측을 보조 모듈로 수행하였다. 지열·수열·바이오·원자력은 공공데이터 운전 기록(지열 히트펌프, 바이오가스 소화조, 원전 계획예방정비 등)으로 AI 적용 가능성을 확인하였다. 사용한 공공데이터 50종은 부록 B에 정리하였다.'),
);

// ── 2. 발전 방식과 기계 기술
push(H1('2. 발전 방식의 분류와 기계 기술'), H2('2.1 출력을 정하는 요인에 따른 분류'),
  P('모든 발전은 "어떤 에너지를 전기로 바꾸는가"로 나뉜다. 터빈과 발전기를 돌리는 회전 기계식(화력·원자력·수력·풍력·지열)과, 태양전지에서 바로 전기를 얻는 직접 변환식(태양광)이 있다. AI 적용 관점에서는 "누가 출력을 정하는가"가 더 중요하다.'),
  TCAP('발전원별 변환 경로와 출력 결정 요인'),
  table(['발전원', '1차 에너지', '변환 경로', '출력을 정하는 것', '제어 가능성'], [
    ['석탄화력', '화학', '연소 → 증기 → 증기터빈', '급전 지시', '가능 (기동 느림)'],
    ['LNG 복합', '화학', '가스터빈 + 배열회수 증기터빈', '급전 지시', '가능 (기동 빠름)'],
    ['원자력', '핵분열', '핵열 → 증기 → 증기터빈', '정비 일정', '제한적 (기저 운전)'],
    ['수력·소수력', '위치', '낙차 → 수차 → 발전기', '유입량·급전 지시', '가능'],
    ['지열', '지열', '지중 열 → 작동유체 기화 → 터빈', '지중 온도·유량', '제한적'],
    ['바이오', '화학', '직접 연소·혼소·가스화', '원료 공급', '가능'],
    ['풍력', '운동', '양력 → 회전 → 발전기', '풍속', '불가'],
    ['태양광', '복사', '광전효과 → 직류 → 인버터', '일사량', '불가'],
  ], [12, 9, 30, 18, 16]),
  H2('2.2 핵심 기계 기술'),
  BL([b('가스복합화력: '), t('가스터빈(브레이턴 사이클)에서 전기를 만들고, 고온 배기가스를 배열회수 증기발생기(HRSG)에서 증기로 바꿔 증기터빈(랭킨 사이클)을 한 번 더 돌린다. 터빈 입구 온도를 높일수록 효율이 오르므로 날개의 내열 소재와 냉각 기술이 핵심이다.')]),
  BL([b('석탄화력: '), t('증기의 압력과 온도를 높일수록 효율이 오르기 때문에 초초임계압(USC) 보일러가 개발되었다.')]),
  BL([b('원자력(가압경수로): '), t('1차 측은 원자로·증기발생기·가압기·냉각재 펌프, 2차 측은 터빈·발전기·복수기로 구성된다. 가압기가 약 150기압을 유지해 냉각재가 약 330℃에서도 끓지 않는다. APR1400은 1,400MW급이며 설계수명이 60년이다.')]),
  BL([b('풍력: '), t('블레이드는 항공기 날개처럼 양력으로 회전력을 만든다. 피치 제어로 강풍 시 과부하를 막고, 기어박스로 저속 회전을 발전기에 맞는 고속 회전으로 바꾸거나 기어박스 없이 직접구동 발전기를 쓴다.')]),
  BL([b('태양광: '), t('셀·모듈이 만든 직류를 인버터가 교류로 바꾼다. 추적장치로 패널 방향을 조절하고, 온도가 오르면 효율이 떨어지므로 방열 구조와 표면 오염 관리가 발전량에 영향을 준다.')]),
  BL([b('지열·소수력: '), t('지열은 생산정·주입정 또는 지중 열교환 루프로 열을 회수해 증기 또는 바이너리(유기 작동유체) 터빈을 돌린다. 소수력은 낙차·유량에 맞는 수차(펠톤·프란시스·카플란)와 취수 스크린·유량 밸브가 연속 운전을 뒷받침한다.')]),
  BL([b('바이오: '), t('전용 보일러 연소, 석탄과의 혼소, 바이오매스를 가스로 바꿔 엔진·터빈에 공급하는 가스화 방식이 있다.')]),
  P([b('효율과 이용률의 구분. '), t('효율은 들어온 에너지 중 전기로 바뀐 비율이고, 이용률은 설비를 정격으로 쉬지 않고 돌렸을 때 대비 실제 생산량의 비율이다. 본 과제의 데이터에서 태양광 발전소의 일별 이용률 중앙값은 '), b(`${pct(R.komipo_fix.cf_median['태양광'])}%`), t(`, 연료전지는 `), b(`${pct(R.komipo_fix.cf_median['연료전지'])}%`), t('였다. 모듈 효율이 20%라는 것과 이용률이 14%라는 것은 전혀 다른 이야기다.')]),
);

// ── 3. 한계
push(H1('3. 하드웨어의 한계'), H2('3.1 물리 법칙의 상한'),
  BL([b('카르노 효율(열기관): '), t('η = 1 − Tc / Th. 고온 열원의 절대온도 Th를 올려야 효율이 오르지만, 소재의 열화·부식·열응력 때문에 무한히 올릴 수 없다. 화력과 원자력 모두 이 한계를 가진다.')]),
  BL([b('베츠 한계(풍력): '), t('바람의 운동에너지를 모두 빼앗으면 터빈 뒤로 공기가 흐르지 못한다. 이상적인 터빈도 바람 에너지의 최대 약 59.3%만 추출할 수 있다.')]),
  BL([b('쇼클리–퀘이서 한계(태양광): '), t('단일접합 태양전지는 흡수하지 못하는 파장과 열 손실 때문에 이론 효율이 약 33%에 머문다. 다중접합·탠덤 셀은 이 한계를 넘을 수 있지만 비용이 크다.')]),
  H2('3.2 한계의 네 가지 유형과 AI의 역할'),
  P('한계를 유형별로 나누면, 하드웨어로 풀 수 없는 문제와 AI가 대신 줄일 수 있는 문제가 구분된다.'),
  TCAP('한계 유형과 AI 대응'),
  table(['유형', '내용', '하드웨어로 해결?', 'AI 대응'], [
    ['① 열역학적 한계', '카르노, 베츠 59.3%, 쇼클리–퀘이서 약 33%', '불가 (물리 법칙)', '범위 밖 — AI로도 못 바꿈'],
    ['② 간헐성·불확실성', '출력이 날씨에 따라 정해짐', '불가', '발전량 예측 (6장)'],
    ['③ 열화·고장', '모듈 열화, 베어링·기어 마모, 원전 출력 저하', '부분적 (비용 증가)', '이상탐지·예지정비 (7장)'],
    ['④ 계통 통합', '관성 감소, 출력제한, 화력의 부하 추종 부담', '부분적 (ESS 등)', '추종 운전·운영 최적화 (7장)'],
  ], [16, 34, 18, 26]),
  P([t('핵심은 '), b('"간헐성(변동) 자체는 없앨 수 없지만, 불확실성(미리 모름)은 줄일 수 있다"'), t('는 점이다. 예비력 확보, 급전 계획 오차, 출력제한은 모두 "미리 모른다"는 데서 생기는 비용이다.')]),
  H2('3.3 발전원별 현장 사례'),
  TCAP('조사 자료와 데이터에서 확인한 발전원별 한계'),
  table(['발전원', '한계 사례', '유형'], [
    ['화력', '효율을 올리려면 온도·압력을 올려야 하고, 견디는 소재가 비싸다', '①'],
    ['원자력', `한빛 5호기 연간 이용률 2020년 ${f1(NU.hanbit5['2020'])}%, 2021년 ${f1(NU.hanbit5['2021'])}%, 2023년 ${f1(NU.hanbit5['2023'])}% (본 과제 데이터)`, '③'],
    ['원자력', `운영 원전 ${NU.operating_units}기 중 ${NU.expire_by_2030.length}기의 설계수명 만료일이 2030년 말 이내 (2025.6 현황표, 이미 지난 호기 포함)`, '③'],
    ['풍력', '풍속 변화에 따른 반복 하중 → 베어링·기어 피로', '③'],
    ['태양광', '야간·구름에 따른 변동, 온도 상승 시 효율 감소', '②'],
    ['지열', '장기 열 추출 시 지중 온도 저하, 스케일·부식', '③'],
    ['소수력', '갈수기·홍수기 유량 변동, 토사에 의한 수차 마모', '② ③'],
    ['바이오', '원료 수분 편차, 가스화 타르, 원료 수급', '③'],
  ], [12, 70, 10]),
);

// ── 4. 시스템 설계
push(H1('4. 시스템 설계'), H2('4.1 핵심 결정: 발전원마다 다른 문제로 푼다'),
  P('모든 발전원에 같은 예측 모델을 쓰지 않는다. 출력을 정하는 요인이 다르면 문제의 수학적 형태도 다르기 때문이다. 원자력이나 연료전지처럼 출력이 날씨와 무관하고 거의 일정한 전원은 "예측"할 것이 없다. 대신 정상 운전 패턴을 기준선으로 삼아 그로부터 벗어나는 순간을 잡는 "이상탐지"가 의미 있는 문제다.'),
  TCAP('발전원별 문제 유형 분리'),
  table(['발전원', '문제 유형', '입력', '본 과제 구현'], [
    ['태양광', '회귀 예측 (하루 전)', '기상 예보 항목, 태양 고도, 과거 발전량', 'LightGBM + 예측구간 (6장)'],
    ['풍력', '회귀 예측 (풍속³ 비선형)', '풍속·풍향 예보', '설계만 (데이터 부족)'],
    ['수력·소수력', '느린 유입량 예측', '누적 강수량', '설계만'],
    ['화력', '잔여수요 추종', '수요 예측, 재생에너지 예측', '수요–발전 상관 분석 (7.2)'],
    ['연료전지·원자력', '이상탐지', '정상 운전 출력 패턴', '연료전지 일별 이상탐지 (7.1), 원전 연간 사례 (7.3)'],
  ], [14, 20, 32, 30]),
  H2('4.2 처리 흐름'),
  P('① 수집(공공데이터 CSV) → ② 점검·보정(중복, 단위, 열 이름, 결측) → ③ 이용률 변환과 피처 생성 → ④ 모델 학습(시간 순서 분할) → ⑤ 평가(기준선 대비 Skill Score) → ⑥ 예측구간 보정 → ⑦ 결과 그림·표. 모든 단계는 energy/audit.py와 energy/analyze.py 두 스크립트로 재현된다(부록 A).'),
  H2('4.3 사용 데이터'),
  TCAP('수집한 공공데이터 10종'),
  table(['데이터', '기간·단위', '규모', '용도'], [
    ['시도별 시간별 태양광 발전량·기상 학습데이터', '2020.1~2024.12, 1시간', `17개 시도, ${solarAud.rows.toLocaleString()}행`, '태양광 예측 (주 데이터)'],
    ['시도별 태양광 발전량 공식 예측값', '2024.12.2 하루, 1시간', '17개 시도', '공식 예측과 비교, 계량 비중'],
    ['한국중부발전 발전설비별 일별 발전량', '2023.11~2026.8, 1일', `${AU.komipo_daily.plants}개 설비`, '연료전지 이상탐지, 태양광 저하 탐지'],
    ['시간별 전력수요', '2017~2021, 1시간', `${AU.demand_hourly.days}일`, '화력 추종 분석'],
    ['지역·연료원별 화력 발전량', '2018.1~2022.6, 1일', `${AU.fuel_daily.rows.toLocaleString()}행`, '화력 추종 분석'],
    ['태안 화력 호기별 발전량', '2022.12~2023.12, 1일', '10개 호기', '석탄 기저 운전 확인'],
    ['원전 호기별 연간 발전량·이용률', '2014~2025, 1년', `${NU.n}행`, '원자력 사례'],
    ['원전 호기별 연간 발전량(누계 포함)', '2019~2025, 1년', '28개 호기', '교차 검증'],
    ['원전 호기 현황', '2025.6 기준', '32개 호기', '설계수명 분석'],
    ['일별 전력수급 현황', '2025, 1일', '365일', '수급·예비율 배경'],
  ], [34, 22, 18, 26]),
  H2('4.4 피처와 누수 방지'),
  BL('시간: 시각·일자를 sin/cos로 변환 (23시와 0시가 가깝다는 것을 모델이 알도록).'),
  BL('천문: 대기권 밖 일사량 계산값 (태양 고도에 따른 결정론적 성분).'),
  BL('기상 예보 항목: 기온, 습도, 풍속, 운량, 강수, 적설 — 기상청 단기예보에 있는 항목만 사용.'),
  BL('과거 발전량: 24시간 전, 168시간(1주) 전 이용률. 하루 전 예측에서 알 수 없는 1시간 전 값 등은 쓰지 않는다.'),
  BL('학습 2020~2022년, 검증 2023년, 평가 2024년. 시계열을 무작위로 섞으면 미래 정보가 학습에 섞이므로 시간 순서로 나눈다.'),
);

// ── 5. 데이터 점검
const ns = R.night_share_total;
push(H1('5. 데이터 점검과 보정'),
  P('공공데이터는 "받으면 바로 쓸 수 있는 상태"가 아니었다. 학습 전에 모든 파일을 점검해 다음 문제를 찾고 보정하였다. 이 과정이 결과의 신뢰도를 결정한다.'),
  TCAP('발견한 데이터 문제와 처리'),
  table(['#', '데이터', '발견한 문제', '처리'], [
    ['1', '태양광 시간별', `같은 지역·시각이 두 번 들어간 행 ${solarAud.dup_rows.toLocaleString()}개(8.3%). 그중 ${solarAud.dup_keys_value_differs.toLocaleString()}개는 값이 서로 다름(최대 ${f1(solarAud.dup_max_abs_diff_MWh)}MWh 차이)`, '첫 번째 값만 남김'],
    ['2', '태양광 시간별', `해가 없는 시간(대기권 밖 일사량 0)의 발전량이 전체의 ${ns['2021']}%(2021년)`, '평가는 낮 시간만. 원인 추정은 아래'],
    ['3', '태양광 시간별', `관측 일사량이 대기권 밖 일사량보다 큰 행 ${solarAud.ghi_over_extra.toLocaleString()}개, 대부분 17~20시`, '계산값과 관측값의 시각 기준이 저녁에 어긋남. 관측 일사량이 있으면 낮으로 판정'],
    ['4', '중부발전 일별', '2025년 1~6월 발전량만 다른 달의 약 1,000배', `÷1000 보정 (${R.komipo_fix.unit_fixed_rows.toLocaleString()}행)`],
    ['5', '중부발전 일별', '인천연료전지 설비용량이 2026년 3월까지 절반(15,800kW)으로 표기되어 이용률이 1.8', '31,680kW로 통일'],
    ['6', '2025 전력수급', '열 이름이 한 칸씩 밀림 ("감발전력" 열에 공급능력 값)', `2열=공급능력, 3열=최대전력으로 보면 예비력 식이 맞음(최대 오차 ${SP.identity_max_err_MW}MW)`],
    ['7', '원전 두 파일', '신한울 1호기 2022년, 2호기 2024년 발전량이 두 파일에서 다름', '누계 파일은 상업운전 전 시운전 발전량을 포함한 것으로 추정'],
  ], [4, 14, 50, 32]),
  P([b('야간 발전량의 원인 추정. '), t(`해가 진 뒤 발전량 비중은 전국 기준 2020년 ${ns['2020']}%, 2021년 ${ns['2021']}%에서 2024년 ${ns['2024']}%로 줄었다(그림 1). 태양광 연계 ESS는 낮에 충전한 전력을 16시 이후 방전하면 높은 REC 가중치를 받았는데, 이 가중치는 2020년 하반기에 낮아진 뒤 신규 설비에는 폐지되었다. 데이터의 추세가 이 정책 변화 시기와 맞기 때문에, 야간 발전량은 ESS 방전분일 가능성이 높다고 판단한다. 다만 데이터에 ESS 여부가 표시되어 있지 않으므로 확정할 수는 없다.`)]),
  ...FIG('f6_night.png', '해가 없는 시간에 기록된 발전량 비중 (연도별)', 5.2),
);

// ── 6. 실험 결과
push(H1('6. 태양광 발전량 예측 실험'),
  H2('6.1 평가 지표'),
  BL('nMAE, nRMSE: 오차를 설비용량으로 나눈 백분율. 지역마다 설비 규모가 달라도 비교할 수 있다.'),
  BL('Skill Score = 1 − (모델 RMSE ÷ 기준선 RMSE). 기준선은 "어제 같은 시각과 같다"고 보는 Persistence. 0이면 기준선과 같고, 1에 가까울수록 좋다.'),
  BL('평가는 2024년 낮 시간만(해가 있는 시간). 밤의 0을 맞히는 것만으로 성능이 좋아 보이는 착시를 막기 위해서다.'),
  H2('6.2 실험 A — 모델 비교'),
  TCAP('모델별 성능 (2024년, 낮 시간)'),
  table(['모델', 'nMAE (%)', 'nRMSE (%)', 'Skill'], [
    ['Persistence (어제 같은 시각)', f2(A.Persistence.nMAE), f2(A.Persistence.nRMSE), '0.000'],
    ['선형회귀', f2(A['선형회귀'].nMAE), f2(A['선형회귀'].nRMSE), A['선형회귀'].Skill.toFixed(3)],
    ['LightGBM (3회 평균)', f2(A.LightGBM.nMAE), `${f2(A.LightGBM.nRMSE)} ± ${A.LightGBM.nRMSE_std.toFixed(2)}`, A.LightGBM.Skill.toFixed(3)],
  ], [40, 18, 22, 16]),
  P(`LightGBM은 기준선보다 오차를 ${pct(A.LightGBM.Skill)}% 줄였다. 같은 평가에서 선형회귀(${pct(A['선형회귀'].Skill)}%)보다 오차가 작았다. 운량의 영향이 시각·계절에 따라 달라지는 관계를 트리 모델이 더 잘 반영했을 가능성이 있으나, 원인을 따로 검증하지는 않았다. 랜덤 시드를 바꿔 3번 학습한 결과의 표준편차는 ${A.LightGBM.nRMSE_std.toFixed(3)}%p로 결과가 안정적이었다.`),
  ...FIG('f1_models.png', '모델별 nRMSE (2024년 낮 시간)', 5.2),
  H2('6.3 실험 B — 기상 정보가 얼마나 중요한가'),
  TCAP('입력하는 기상 정보 수준에 따른 성능'),
  table(['입력', 'nRMSE (%)', 'Skill'], Object.entries(B).map(([k, v]) => [k.replace(/^B\d /, ''), f2(v.nRMSE), v.Skill.toFixed(3)]), [60, 20, 20]),
  P(`기상 정보 없이 시간·태양 고도·과거 발전량만 쓰면 Skill은 ${f2(B['B0 기상 정보 없음'].Skill)}에 그친다. 기상 예보 항목을 넣으면 ${f2(B[B1k].Skill)}로 뛰고, 예보 항목이 아닌 실측 일사량까지 넣으면 ${f2(B['B2 + 실측 일사량·일조'].Skill)}가 된다. 발전량 예측 성능의 대부분은 모델이 아니라 "날씨를 얼마나 잘 아느냐"에서 나온다.`),
  ...FIG('f2_weather_info.png', '기상 정보 수준별 nRMSE', 5.2),
  P([b('주의할 점. '), t('이 실험의 기상 입력은 그 시각의 관측값이다. 실제 하루 전 예측에서는 내일 날씨를 예보로만 알 수 있으므로 오차가 더 커진다. 따라서 위 숫자는 실제 하루 전 운영 성능이 아니라 관측 기상 조건의 결과다.')]),
  P([t(`참고로 2024년 12월 2일 하루에 대해 공식 하루 전 예측(전날 14시 발표)과 비교하였다. 낮 시간 ${KD.n}개 시도·시각에서 공식 예측의 nRMSE는 ${f2(KD['공식 하루 전 예측'].nRMSE)}%, 기준선은 ${f2(KD.Persistence.nRMSE)}%, 관측 기상을 넣은 우리 모델은 ${f2(KD['우리 모델(관측 기상 입력)'].nRMSE)}%였다. 두 예측은 입력(관측 기상과 예보)과 예측 시스템이 함께 다르고 하루치 비교이므로, 이 차이만으로 운영 성능의 우열이나 기상 예보의 영향을 판단할 수 없다. 과거 예보 자료를 확보해 같은 조건에서 1년 단위로 비교하는 것을 향후 과제로 남긴다.`)]),
  ...FIG('f7_kpx_day.png', '2024년 12월 2일, 17개 시도 합계 실제 발전량과 예측', 5.0),
  H2('6.4 실험 C — 피처 그룹별 기여'),
  TCAP('피처 그룹을 하나씩 추가했을 때의 성능'),
  table(['피처 구성', 'nRMSE (%)', 'Skill'], Object.entries(C).map(([k, v]) => [k, f2(v.nRMSE), v.Skill.toFixed(3)]), [60, 20, 20]),
  P(`시간·지역만으로도 기준선보다 조금 낫지만(Skill ${f2(C['시간·지역'].Skill)}), 결정적인 도약은 기상 예보 항목을 넣을 때 나온다. 대기권 밖 일사량은 시각·날짜 정보와 겹쳐 단독 기여가 거의 없었다. 과거 발전량(lag)은 마지막으로 Skill을 ${f2(C['+ 과거 발전량(lag)'].Skill - C['+ 기상 예보 항목'].Skill)} 더 올렸다. 주 모델의 피처 중요도는 시각(hour_cos) ${R.importance_main.hour_cos}%, 운량 ${R.importance_main.cloud}%, 대기권 밖 일사량 ${R.importance_main.extra}%, 어제 발전량 ${R.importance_main.lag24}% 순이었다.`),
  H2('6.5 실험 D — 이용률 정규화의 효과'),
  P('학습 기간(2020~2022년)과 평가 기간(2024년) 사이에 설비가 크게 늘었다. 발전량(MWh)을 그대로 학습하면 모델은 과거 설비 규모를 기준으로 예측하므로 2024년을 체계적으로 낮게 예측한다. 발전량을 설비용량으로 나눈 이용률로 학습하고 예측 후 다시 곱하면 이 문제가 사라진다.'),
  TCAP('학습 대상에 따른 2024년 성능 (과거 발전량 피처 없이 같은 조건)'),
  table(['학습 대상', 'nRMSE (%)', '치우침 (설비용량 대비 %p)'], [
    ['원시 발전량(MWh)', f2(Dd['원시 발전량(MWh) 학습'].nRMSE), f2(Dd['원시 발전량(MWh) 학습'].bias)],
    ['이용률(발전량 ÷ 설비용량)', f2(Dd['이용률(CF) 학습'].nRMSE), f2(Dd['이용률(CF) 학습'].bias)],
  ], [44, 24, 32]),
  ...FIG('f4_normalize.png', '설비용량 증가(왼쪽)와 학습 대상에 따른 예측 치우침(오른쪽)', 6.2),
  H2('6.6 예측구간 — 불확실성까지 알려주기'),
  P(`점 하나로 "내일 12시 발전량은 X"라고만 하면 사용자는 이를 확정값으로 오해한다. 분위수 회귀로 P10(하위 10%)과 P90(상위 10%) 모델을 따로 학습해 범위를 함께 제시하였다. 처음에는 2024년 실제값의 ${pct(IV.raw_coverage)}%만 범위 안에 들어와 목표 80%보다 좁았다. 2023년 검증 데이터로 범위 폭을 보정하는 분할 conformal 방법을 적용하자 포함률이 ${pct(IV.calibrated_coverage)}%가 되었고, 평균 폭은 설비용량의 ${f1(IV.raw_width)}%에서 ${f1(IV.cal_width)}%로 조금만 넓어졌다.`),
  H2('6.7 잘 맞은 날과 크게 틀린 날'),
  ...FIG('f3_days.png', `전남 ${R.fig_days.good}(맑은 날)과 ${R.fig_days.worst}(크게 틀린 날)의 시간별 예측`, 6.4),
  P(`맑은 날에는 예측이 실제를 잘 따라가고 예측 범위도 좁다. ${R.fig_days.worst}에는 운량 정보로는 예상하지 못한 맑은 오후가 나타나 모델이 크게 낮게 예측했다. 이처럼 크게 틀리는 날이 있다는 것이 "불확실성은 줄일 수 있지만 없앨 수는 없다"는 본 과제의 주장을 뒷받침한다. 또한 맑은 날 19~21시에 실제 발전량이 남아 있는데, 모델은 해가 있는 시간만 예측하므로 이 부분(5장의 야간 발전량)을 놓친다.`),
  H2('6.8 지역별 성능'),
  ...FIG('f5_region.png', '지역별 nRMSE — 기준선(회색)과 AI 예측(청록)', 5.8),
  P(`17개 시도 모두에서 기준선보다 오차가 크게 줄었다. 설비가 가장 큰 전남(${R.region[0].nRMSE}%)과 제주(${R.region.find(r => r.region === '제주').nRMSE}%)가 상대적으로 어려웠다. 넓은 지역에 설비가 흩어져 하나의 기상값으로 대표하기 어려운 것이 한 가지 가능성이지만, 원인은 따로 검증하지 않았다.`),
  H2('6.9 하루 전에 실제로 할 수 있는 성능'),
  P(`지금까지의 성능은 그 시각의 관측 기상을 넣은 결과다. 실제 운영처럼 "전날 14시에 내일을 예측한다"고 가정해, 관측 기상과 24시간 전 값을 빼고 48시간 전·1주 전 값, 시각·날짜, 대기권 밖 일사량만 쓰는 모델을 따로 학습하였다(2023년 상반기로 조기 종료). 2024년 낮 시간 ${SI.test_rows.toLocaleString()}개 시도·시각에서 이틀 전 값을 그대로 쓰는 기준은 ${f1(SI.lag48_baseline.nRMSE)}%, 이 모델은 ${f1(SI.lightgbm.nRMSE)}%였고, 같은 행에서 관측 기상 모델은 ${f1(SI.observed_weather_reference.nRMSE)}%였다. 이 모델은 관측 기상뿐 아니라 24시간 전 값도 빼고 48시간 전 값을 쓰므로, 두 값의 차이를 모두 날씨 효과로 볼 수는 없다. 실제 기상 예보를 넣은 운영 성능은 아직 측정하지 않았고, 과거 예보 자료로 재는 것이 다음 과제다.`),
  P(`같은 조건에서 2023년 하반기 자료로 80% 예측 범위를 보정하자 2024년 포함률은 ${SII.calibrated.coverage_pct}%, 평균 폭은 설비용량의 ${SII.calibrated.mean_width_pp}%였다. 달마다 ${Math.min(...Object.values(SII.by_month).map(v => v.coverage_pct)).toFixed(1)}~${Math.max(...Object.values(SII.by_month).map(v => v.coverage_pct)).toFixed(1)}%로 차이가 있어, 연간 포함률만으로는 계절별 신뢰도를 보장할 수 없다.`),
  H2('6.10 발전소 단위 검증'),
  P(`시도 합계는 발전소마다의 오차가 서로 상쇄될 수 있다. 한국수력원자력의 태양광 ${P2.khnp_solar.plants}곳 시간별 발전량과 인근 기상 자료로 2023~2024년에 학습하고 2025년 낮 시간에 시험하였다. 어제 값 ${f1(P2.khnp_solar.nRMSE.persistence)}%, 기상 없음 ${f1(P2.khnp_solar.nRMSE['기상 없음'])}%, 예보에 있는 항목 ${f1(P2.khnp_solar.nRMSE['예보 항목(기온·습도·풍속·강수)'])}%, 실측 일조·일사까지 ${f1(P2.khnp_solar.nRMSE['+ 실측 일조·일사'])}%였다. 시도 실험과 평가 연도·자료가 달라 오차 크기를 직접 비교하기는 어렵지만, 관측 기상 항목을 더할수록 오차가 줄어드는 순서는 같았다.`),
  ...FIG('f21_khnp_solar.png', `한수원 태양광 ${P2.khnp_solar.plants}곳, 2025년 낮 시간 nRMSE`, 5.4),
);

// ── 7. 이상탐지·추종
const fc = R.fuelcell, sj = fc['세종연료전지'];
const fcRows = Object.entries(fc).map(([k, v]) => [k, `${pct(v.cf_median)}%`, v.alerts, v.events]);
push(H1('7. 이상탐지와 추종 분석'),
  H2('7.1 연료전지 이상탐지'),
  P(`연료전지는 날씨와 무관하게 거의 일정한 출력으로 운전된다(이용률 중앙값 ${pct(R.komipo_fix.cf_median['연료전지'])}%). 따라서 원자력처럼 "예측"보다 "정상 패턴에서 벗어남"을 잡는 것이 의미 있다. 각 설비의 과거 28일 이용률 중앙값을 정상 패턴으로 삼고, 그보다 (1) 통계적으로 크게 낮고(과거 편차의 3배 초과) (2) 설비용량의 15%p 이상 떨어진 날을 이상으로 표시하였다. 두 조건을 함께 쓰는 이유는, 출력이 아주 일정한 설비에서는 통계 기준만 쓰면 사소한 변동에도 알림이 쏟아지기 때문이다(통계 기준만 썼을 때는 설비별로 전체 날짜의 5.6~19.4%가 알림이었다).`),
  TCAP('연료전지 설비별 이상 알림 (2023.11~2026.8)'),
  table(['설비', '이용률 중앙값', '알림 일수', '알림 구간 수'], fcRows, [40, 20, 20, 20]),
  ...FIG('f8_fuelcell.png', '세종연료전지의 일별 이용률과 이상 알림', 6.2),
  P(`세종연료전지는 ${sj.events}번의 출력 급락 구간이 잡혔고, 2026년 4월에는 이용률 0인 기록이 있었다(실제 정지 원인은 운전 기록으로 확인해야 한다). 또한 2024년 0.9 안팎이던 이용률이 2026년 0.55~0.65까지 서서히 내려오는 장기 추세도 보인다. 이런 점진적 저하는 28일 기준선이 함께 따라 내려가므로 일별 알림으로는 잡히지 않는다. 장기 열화 감지에는 연 단위 기준선을 따로 두어야 한다. 정비 기록이 없어 알림이 실제 고장인지는 검증하지 못했다.`),
  P([b('태양광 발전소 저하 탐지. '), t(`같은 날 비교 집단의 이용률 중앙값으로 나누면 공통된 날씨 영향을 줄일 수 있다(국지 날씨와 설비 차이는 남는다). 같은 지역(충남·인천·제주 등) 발전소끼리 비교하되 지역 표본이 적은 설비는 전국 묶음과 비교했고, 이 비율이 평소의 절반 아래로 떨어진 날을 표시하였더니, ${R.solar_peer.plants}개 발전소에서 ${R.solar_peer.events}개 구간이 후보로 잡혔다. 처음에 전국 중앙값과 비교했을 때는 날씨가 다른 제주 발전소들에 알림이 몰렸는데, 지역별로 비교하자 크게 줄었다. 비교 대상을 잘 고르는 것이 이상탐지의 핵심이다.`)]),
  H2('7.2 화력은 수요를 따라간다'),
  P(`${FO.period}의 하루 전력수요와 연료원별 화력 발전량을 비교하였다. 하루 수요와의 상관계수는 LNG ${FO.corr.LNG}, 석탄 ${FO.corr['석탄']}, 유류 ${FO.corr['유류']}였다. 변동계수(표준편차 ÷ 평균)는 수요 ${FO.cv.demand_GWh}, 석탄 ${FO.cv['석탄']}, LNG ${FO.cv.LNG}로, LNG가 수요보다 2.5배 크게 출렁였다. 석탄은 기저 운전에 가깝고(태안 화력 10개 호기 평균 이용률 ${pct(R.taean.cf_mean)}%), 분석 기간에 LNG 발전량이 비교한 연료 중 수요와 가장 강하게 함께 움직였다. 재생에너지 변동을 LNG가 얼마나 보완하는지는 별도 분석이 필요하다.`),
  ...FIG('f9_follow.png', '하루 전력수요와 LNG·석탄 발전량 (7일 이동평균)', 6.2),
  P(`2025년 육지에서 전기 도매가격(SMP)을 정한 발전기의 연료는 LNG가 ${P3.smp_fuel_2025['육지'].LNG}%, 유연탄이 ${P3.smp_fuel_2025['육지']['유연탄']}%였다. 수요 변화를 마지막에 맞추는 발전기가 가격을 정하므로, LNG가 추종 전원이라는 해석과 맞는다.`),
  H2('7.3 LNG 일별 발전량 예측'),
  P(`2018~2020년으로 학습하고 2021년 ${LP.test_days}일로 시험하였다(일평균 LNG ${f1(LP.test_mean_GWh)} GWh). 어제 값을 그대로 쓰면 오차(nRMSE)가 ${f1(LM[kP].nRMSE)}%, 지난주 같은 요일 값은 ${f1(LM['전주 같은 요일 값'].nRMSE)}%였다. 전날까지의 정보(전날 수요, 최근 LNG, 요일, 월)만 쓴 선형회귀는 ${f1(LM[kR].nRMSE)}%로 오차를 ${pct(LM[kR].Skill)}% 줄였다. 수요 정보를 뺀 모델도 ${f1(LM[kN].nRMSE)}%로 거의 같았다(이 조건은 전날 집계가 예측 시각까지 나온다고 가정한다). 그날 실제 수요를 넣으면 ${f1(LM[kU].nRMSE)}%이지만 수요는 하루가 끝나야 알 수 있으므로 사후 참고값이다. 모든 조건에서 GBDT보다 선형회귀가 나았는데, 학습 기간이 3년으로 짧고 관계가 거의 선형이기 때문으로 보인다.`),
  ...FIG('f11_lng_pred.png', '2021년 일별 LNG 발전량 — 실제와 예측', 6.2),
  H2('7.4 원자력 — 출력 저하와 정비'),
  P(`원전 연간 이용률의 연도별 중앙값은 대체로 73~87%이지만, 한빛 5호기는 2020년 ${f1(NU.hanbit5['2020'])}%, 2021년 ${f1(NU.hanbit5['2021'])}%, 2023년 ${f1(NU.hanbit5['2023'])}%로 크게 떨어졌다. 아래에서 보듯 이 해들은 계획예방정비가 길었던 해와 겹친다. 또한 2025년 6월 현황표에서 운영으로 분류된 원전 ${NU.operating_units}기 중 ${NU.expire_by_2030.length}기는 설계수명 만료일이 2030년 말 이내다(이미 만료일이 지난 호기 포함). 노후 설비가 늘수록 상태 감시의 필요성은 커진다.`),
  ...FIG('f10_nuclear.png', '원전 연간 이용률: 전체 호기 중앙값과 한빛 5호기', 5.6),
  P(`한국수력원자력의 계획예방정비 기록을 호기별 이용률과 맞춰 보면 그해 정비 일수와 이용률의 상관계수가 ${P1.nuclear_outage.corr_outage_days_vs_cf}였다. 이용률 50% 미만이던 ${P1.nuclear_outage.low_cf_cases}건은 그해 정비가 평균 ${f1(P1.nuclear_outage.low_cf_mean_outage_days)}일, 나머지는 ${f1(P1.nuclear_outage.others_mean_outage_days)}일이었다. 한빛 5호기도 2020년 ${P1.nuclear_outage.hanbit5['2020'].outage_days}일, 2021년 ${P1.nuclear_outage.hanbit5['2021'].outage_days}일, 2023년 ${P1.nuclear_outage.hanbit5['2023'].outage_days}일 정비 중이었다. 정비 기록이 연결되지 않은 호기·연도는 정비 일수 0으로 처리했다. 원전에서는 출력 예측보다 정비 기록과 설비 상태를 함께 보는 것이 이용률을 이해하는 열쇠이며, 설비 상태 자료를 확보하면 정비 판단을 돕는 방법을 시험할 수 있다.`),
  ...FIG('f15_nuclear_outage.png', '호기·연도별 계획예방정비 일수와 연간 이용률', 5.6),
  H2('7.5 풍력·소수력 — 같은 규칙도 발전원마다 다르게 작동한다'),
  P(`연료전지 규칙(15%p 하락)과 비율 규칙(평소의 절반 이상 하락)을 한국중부발전 풍력·소수력에 적용하였다. 두 규칙 모두 평소 변동보다 크게 낮은 날(3σ)만 대상으로 하고, 비율 규칙은 기준 이용률이 3% 이상일 때만 쓴다. 판정 가능한 제주상명풍력은 ${WHd.plants['제주상명풍력'].days}일 동안 두 규칙 모두 0건이었고(양양풍력은 기록 1일로 판정 불가), 바람에 따라 매일 크게 출렁여 발전량만으로는 "평소와 다른 날"이 드러나기 어렵다. 소수력은 15%p 규칙에서 보령화력소수력#2가 ${WHd.plants['보령화력소수력#2'].alerts}일(${WHd.plants['보령화력소수력#2'].events}구간)로 가장 많았으나 강수·유량과 대조하기 전에는 갈수기와 구분할 수 없다.`),
  ...FIG('f12_wind_hydro.png', '풍력·소수력 설비별 이상 후보 알림 일수', 5.6),
  P(`풍속과 출력이 함께 기록된 한국서부발전 풍력발전소 운전 기록(SCADA)으로 다시 보았다. 운전 중인 시간으로 풍속별 출력 곡선을 만들면, 장흥풍력은 이 실험의 과거 출력 기준(같은 호기 24시간 전) ${f1(P2.wind_scada['장흥풍력'].nRMSE_persistence_24h)}%에서 실제 풍속+곡선 ${f1(P2.wind_scada['장흥풍력'].nRMSE_curve_with_actual_wind)}%로 오차가 줄었다. 화순풍력은 바람이 충분한데(초속 5~12m) 이용률이 1% 이하인 시간이 일부 호기에 몰려 있었다(${Object.entries(P2.wind_scada['화순풍력'].stopped_by_unit).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([k, v]) => k + '호기 ' + v.toLocaleString() + '시간').join(', ')}). 남부발전 성산풍력 10기의 일평균 풍속에서도 1호기·5호기만 단지 평균보다 자주 약했다(${P3.seongsan_wind.low_days_by_unit['성산1호기']}일·${P3.seongsan_wind.low_days_by_unit['성산5호기']}일). 풍력은 같은 단지의 호기끼리 비교하면 "평소와 다른 호기"가 보인다. 멈춘 이유가 고장인지 출력제어인지는 기록과 대조해야 한다.`),
  ...FIG('f19_wind_scada.png', '장흥풍력 풍속–출력 곡선(왼쪽)과 풍속을 알 때의 오차(오른쪽)', 6.4),
  H2('7.6 연료전지의 장기 저하'),
  P(`7.1절의 28일 기준선은 천천히 떨어지는 저하를 따라가 놓친다. 처음 90일을 고정 기준으로 두고 작은 하락을 누적하는 누적합(CUSUM) 규칙을 시험하자 세종연료전지는 ${CU.plants['세종연료전지'].first_alert_date}부터 지속 저하 후보로 잡혔다. 다만 기준 기간(2023.11~2024.1)이 겨울이라 다른 설비도 대부분 일찍 경보가 켜져, 기준 기간 설정이 과제로 남는다. 한국남부발전 연료전지 월별 실적에서도 ${P2.kospo_fuelcell.declining_over_1pp_per_year.length}개 계열이 해마다 이용률이 1%p 넘게 떨어졌고, 동서발전 호기별 실적에서 열효율이 최근 12개월보다 2%p 이상 떨어진 달이 가장 많은 설비도 연료전지였다. 장기 저하는 한 설비만의 일이 아니다.`),
  ...FIG('f22_fuelcell_trend.png', '남부발전 연료전지 월별 이용률(3개월 중앙값)', 5.8),
  H2('7.7 지열·바이오에도 같은 방법을'),
  P(`국립세종수목원 지열 히트펌프의 시간별 운전 기록(${P1.geothermal.period}, ${P1.geothermal.buildings.length}개 건물)에서 생산 열량을 소비 전력으로 나눈 효율(COP)은 운전 중 중앙값 ${P1.geothermal.cop_median}였다. 건물별로 앞선 유효 관측일 28개의 중앙값과 비교해 효율이 30% 넘게 낮은 날을 표시하니, 판정한 건물·날짜 기록 ${Object.values(P1.geothermal.judged_days).reduce((a, v) => a + v, 0).toLocaleString()}건 중 ${Object.values(P1.geothermal.cop_drop_alert_days).reduce((a, v) => a + v, 0)}건이었다. 광주 하수처리장 소화조의 바이오가스 생산량에서는 평소보다 40% 이상 줄어든 날이 ${P3.biogas_digester.alert_days}일이었다. 바이오 연료 분석 ${P1.biomass.samples}건에서는 수분이 많을수록 발열량이 낮았다(순위 상관 ${P1.biomass.spearman_moisture_heating_value}). 운전 데이터만 있으면 연료전지와 같은 "이상 후보 알림"을 지열·바이오에도 쓸 수 있다.`),
  ...FIG('f13_geothermal.png', '국립세종수목원 지열 히트펌프 일별 COP와 입수온도', 6.4),
);

// ── 7-2. 사용량에 따른 발전 계획 AI (목표)
const PLn = R.plan, PLw = PLn.with_weather;
push(H2('7.8 사용량(수요)에 맞춘 발전 계획 AI'),
  P(`본 과제의 목표는 전기를 얼마나 쓸지(수요)를 미리 알고, 그에 맞춰 발전 계획을 세우고, 발전원별 발전량을 예측해 낭비 없이 생산하는 것이다. 2025년 시간별 전국 전력수요와 태양광·풍력 거래량으로 시제품을 만들었다. 전날 14시에 ① 내일 수요, ② 내일 태양광·풍력을 예측하고, ③ 수요에서 태양광·풍력을 뺀 순수요(나머지 발전소가 채울 양)를 구한 뒤, ④ 원자력(설비 ${PLn.plan.nuclear_basis.split(' ')[2]} MW × 2025 이용률 중앙값, 약 ${PLn.plan.nuclear_MW.toLocaleString()} MW로 가정)을 먼저 놓고 나머지를 출력을 조절할 수 있는 발전(석탄·LNG 등)으로 채운다. AI는 수요의 절대 크기 대신 "이틀 전 하루 평균 대비 비율"을 배우게 하고, 매달 그 전날까지의 자료로 다시 학습하였다(처음에 수요 자체를 1~8월 자료로 학습했을 때는 9~12월 수준을 맞추지 못해 기준보다 나빴다).`),
  P(`2025년 9~12월 시험에서 수요 예측 오차(평균 절대 백분율)는 지난주 같은 시각 값을 그대로 쓰는 방법 ${PLn.demand['지난주 같은 시각'].MAPE_pct}%에서 AI ${PLn.demand.AI.MAPE_pct}%로 줄었다. 예측이 틀릴 때를 대비해 대기해야 하는 발전량(시간의 95%를 버티는 크기)은 순수요 기준 ${PLn.net['지난주 같은 시각'].reserve_P95_MW.toLocaleString()} MW에서 ${PLn.net.AI.reserve_P95_MW.toLocaleString()} MW로 약 ${PLn.reserve_saving_MW.toLocaleString()} MW 줄었고, 실제보다 많이 준비한 전력량은 ${PLn.over_saving_GWh.toLocaleString()} GWh 줄었다. 태양광·풍력은 날씨 예보 없이 과거 값만 써서 기준과 비슷했다(태양광 설비용량 대비 오차 ${PLn.solar.AI_nMAE_pct}% vs ${PLn.solar['지난주_nMAE_pct']}%, 풍력 ${PLn.wind.AI_nMAE_pct}% vs ${PLn.wind['지난주_nMAE_pct']}%). 발전기별 비용·기동 제약을 반영하지 않은 시제품이며, 날씨 예보와 시간별 SMP를 넣는 것이 다음 단계다.`),
  ...FIG('f27_plan_day.png', `${PLn.example_day} 발전 계획(전날 14시 작성)과 순수요 예측`, 6.4),
  ...FIG('f28_plan_reserve.png', '예측이 틀릴 때를 대비해 대기할 발전량과 실제보다 많이 준비한 전력량', 6.0),
  P(`관측 날씨를 넣은 참고 실험에서는 기상청 ASOS의 일사량·일조시간·전운량·기온을 태양광 예측에, 풍속을 풍력 예측에, 기온·습도를 수요 예측에 사용했다. 날씨 없이 학습한 AI와 관측 날씨를 쓴 AI를 2025년 9~12월 같은 ${PLw.test_hours.toLocaleString()}시간에서 비교했다. 대기 발전량(P95)은 ${PLn.net.AI.reserve_P95_MW.toLocaleString()} → ${PLw.net.AI.reserve_P95_MW.toLocaleString()} MW, 실제보다 많이 준비한 전력량은 ${PLn.net.AI.over_GWh.toLocaleString()} → ${PLw.net.AI.over_GWh.toLocaleString()} GWh였다. 수요의 평균 절대 백분율 오차는 ${PLn.demand.AI.MAPE_pct}% → ${PLw.demand.AI.MAPE_pct}%, 설비용량 대비 평균 절대 오차는 태양광 ${PLn.solar.AI_nMAE_pct}% → ${PLw.solar.AI_nMAE_pct}%, 풍력 ${PLn.wind.AI_nMAE_pct}% → ${PLw.wind.AI_nMAE_pct}%였다. ${PLw.caution}`),
  ...FIG('f29_plan_weather.png', '관측 날씨 사용 여부에 따른 대기 발전량과 태양광·풍력 예측 오차', 6.4),
);

// ── 8. 공공데이터 50종으로 확인한 근거
const RS = P1.renewables_2025.by_source, CUy = P1.curtailment.days_by_year, VAL = P1.forecast_value, DM = P3.demand_2025;
push(H1('8. 공공데이터 50종으로 확인한 근거'),
  P('처음 받은 자료 가운데 공공데이터포털에서 다시 받을 수 있는 9종에, 새로 찾은 41종을 더해 모두 50종을 분석에 썼다(부록 B). 새 자료는 직접 검색으로 16종, GPT 웹 조사로 25종을 찾았고, 내려받을 수 없는 오픈API·외부 포털 자료는 제외하였다.'),
  H2('8.1 출력을 누가 정하는가 — 2025년 실적'),
  P(`전력거래소의 2025년 시간별 신재생 실적으로, 어제 같은 시각 값을 그대로 쓸 때의 오차(설비용량 대비)를 발전원별로 비교하였다. 연료전지 ${f1(RS['연료전지'].dayahead_persistence_nRMSE)}%, 소수력 ${f1(RS['소수력'].dayahead_persistence_nRMSE)}%, 바이오매스 ${f1(RS['바이오매스'].dayahead_persistence_nRMSE)}%는 어제 값으로도 거의 맞지만, 태양광 ${f1(RS['태양광'].dayahead_persistence_nRMSE)}%(밤 포함), 풍력 ${f1(RS['풍력'].dayahead_persistence_nRMSE)}%는 그렇지 않다. 전력수요는 지난주 같은 요일 값으로도 최대전력 대비 ${DM.persistence168_nRMSE_of_peak}%로 작다. 어제 값 기준선의 오차가 풍력·태양광에서 크다는 것은 이들 발전원에서 예측의 여지가 크다는 단서다(수요 오차는 최대전력 대비라 분모가 다르다). 4장의 설계, 즉 설비·수요가 출력을 정하는 발전원에는 "평소와 다름"을, 날씨가 정하는 발전원에는 "미래 예측"을 맡기는 방향과 맞는다.`),
  ...FIG('f16_source_variability.png', '2025년 발전원별 "어제 값" 예측 오차', 5.6),
  H2('8.2 예측이 필요한 이유가 커지고 있다'),
  P(`육지 태양광 출력제어(발전을 강제로 멈추게 하는 조치)는 2024년 ${CUy['육지 태양광 출력제어횟수']['2024'] || 0}일에서 2025년 ${CUy['육지 태양광 출력제어횟수']['2025'] || 0}일로, 육지 풍력은 ${CUy['육지 풍력 출력제어횟수']['2024'] || 0}일에서 ${CUy['육지 풍력 출력제어횟수']['2025'] || 0}일로 늘었다. 제주 전력거래량에서 태양광·풍력·급전가능 재생에너지의 합계 비중은 2010년 ${P2.jeju_fuel.renewable_share_pct_by_year['2010']}%에서 2025년 ${P2.jeju_fuel.renewable_share_pct_by_year['2025']}%가 되었다. 변동 전원이 늘면서 하루 전 예측의 중요성이 커지는 현황이다(출력제어의 원인과 예측 개선 효과는 별도 분석이 필요하다).`),
  ...FIG('f17_curtailment.png', '재생에너지 출력제어 일수', 5.6),
  H2('8.3 예측 개선을 돈으로 환산하면 (참고)'),
  P(`관측 기상 실험의 nMAE 차이(${VAL.nMAE_reduction_pp}%p)를 2024년 낮 시간 설비용량 합에 적용하면 약 ${VAL.abs_error_reduction_GWh.toLocaleString()} GWh이고, 월별 통합 SMP의 2024년 단순평균 ${VAL.smp_2024_won_per_kWh}원/kWh를 곱하면 약 ${Math.round(VAL.value_100M_won).toLocaleString()}억 원 규모다. 각 시각의 실제 오차 감소량을 합한 값이 아닌 단순 환산이며, 실제 절감액으로 해석할 수 없다. 예측 오차를 계통 비용으로 정확히 환산하는 것은 향후 과제로 남긴다.`),
);

// ── 8. 확장안·결론
push(H1('9. 발전원별 AI 적용 확장안'),
  P('구현하지 못한 발전원에도 같은 원리(예측·추종·이상탐지)를 적용할 수 있다. 아래는 조사 자료의 한계에 맞춘 적용 후보이며, 실제 사례 확인이 필요하다.'),
  TCAP('발전원별 AI 적용 후보'),
  table(['발전원', '한계', 'AI 적용 후보'], [
    ['풍력', '출력 변동, 기어·베어링 마모', '풍속 예보 기반 발전량 예측, 진동 데이터 예지정비, 후류를 고려한 단지 제어'],
    ['지열', '지중 온도 저하, 스케일·부식', '온도·유량 데이터로 열 추출량 조절, 스케일 발생 시점 예측'],
    ['소수력', '유량 변동, 수차 마모', '강수·수문 데이터로 유입량 예측, 진동 기반 마모 감지'],
    ['화력', '소재 한계로 효율 정체', '연료·공기 비율 연소 최적화, 재생에너지 예측과 연계한 추종 운전'],
    ['원자력', '노후화, 출력 저하', '정상 출력 패턴 대비 이상탐지, 디지털 트윈 기반 상태 감시'],
    ['바이오', '원료 수분 편차, 타르', '원료 품질 예측에 따른 연소 조건 자동 조절'],
  ], [12, 26, 62]),
  H1('10. 결론'),
  H2('10.1 요약'),
  BL('공공데이터를 점검해 중복·단위·열 이름 등 7건의 문제를 찾아 보정했고, 분석 자료를 50종으로 넓혔다. 처음 받은 자료를 공공데이터포털에서 다시 내려받아 돌려도 같은 결과가 재현되었다.'),
  BL(`하루 전 태양광 예측에서 LightGBM은 기준선 대비 오차를 ${pct(A.LightGBM.Skill)}% 줄였다(nRMSE ${f1(A.Persistence.nRMSE)}% → ${f1(A.LightGBM.nRMSE)}%).`),
  BL(`이용률로 학습해 설비 증설에 따른 평균 치우침을 ${f1(Dd['원시 발전량(MWh) 학습'].bias)}%p에서 +${f1(Dd['이용률(CF) 학습'].bias)}%p로 줄였다.`),
  BL(`예측구간을 conformal 방법으로 보정해 포함률을 목표 80%에 맞췄다(${pct(IV.calibrated_coverage)}%).`),
  BL('출력이 일정한 기저형 전원(연료전지)에는 이상 후보 알림을, 화력에는 수요 추종 분석을 적용해 "발전원마다 AI가 푸는 문제가 다르다"는 설계를 데이터로 확인하였다.'),
  BL(`같은 평가 행에서 전날 14시 발행을 가정한 기상 미사용 모델은 ${f1(SI.lightgbm.nRMSE)}%, 관측 기상 참고 모델은 ${f1(SI.observed_weather_reference.nRMSE)}%였다. 실제 예보를 넣은 성능은 측정하지 않았다. 발전소 ${P2.khnp_solar.plants}곳에서도 관측 기상을 더할수록 오차가 주는 순서를 확인하였다.`),
  BL(`LNG 일별 예측은 전날까지의 정보로 어제 값 대비 오차를 ${pct(LM[kR].Skill)}% 줄였고, 원전은 정비 일수와 이용률의 상관이 ${P1.nuclear_outage.corr_outage_days_vs_cf}였다.`),
  BL('풍력은 발전량만으로는 이상을 가릴 수 없었지만, 풍속 기록이나 같은 단지 호기끼리의 비교로 "평소와 다른 호기"를 찾을 수 있었다.'),
  H2('10.2 AI가 할 수 있는 것과 없는 것'),
  P('AI는 카르노·베츠·쇼클리–퀘이서 한계를 넘지 못한다. 설비 하나의 효율을 1%p 올리는 일은 여전히 소재와 기계 기술의 몫이다. AI가 하는 일은 이미 있는 설비가 "언제, 얼마나" 전기를 만들지 미리 알려주고, 고장 신호를 일찍 잡아, 설비를 더 짓지 않고도 운영 손실을 줄이는 것이다.'),
  H2('10.3 한계'),
  BL('주 실험의 기상 입력은 관측값이며, 실제 기상 예보를 넣은 하루 전 운영 성능은 측정하지 않았다.'),
  BL('주 실험은 시도 단위 합계라 개별 발전소의 변동이 상쇄된다. 발전소 54곳 검증(6.10절)으로 일부 보완했지만, 계량 설비(약 29%)만 포함한다는 한계는 남는다.'),
  BL('야간 발전량(ESS 방전 추정)을 분리하지 못했다.'),
  BL('이상 후보 알림을 정비 기록과 대조하지 못해 실제 고장 여부를 검증하지 못했다. 공개된 예방정비 기록은 화력·복합 설비뿐이라 연료전지·풍력 알림과 맞출 수 없었다.'),
  BL('예측 오차 개선을 SMP로 단순 환산했을 뿐(8.3절), 예비력·불균형 정산 같은 실제 비용으로는 환산하지 못했다.'),
  BL('LNG 예측 시험은 2021년 한 해뿐이고, 연료전지 장기 저하(CUSUM)는 기준 기간 설정에 민감하다.'),
  H2('10.4 향후 과제'),
  BL('기상청 단기예보 과거 자료를 확보해 "관측 기상 vs 예보 기상" 격차를 1년 단위로 측정'),
  BL('ESS 연계 여부 데이터를 결합해 태양광 순수 발전량과 방전량 분리'),
  BL('풍력은 풍속 예보와 출력 곡선을 결합한 예측, 같은 단지 호기 비교 알림으로 확장'),
  BL('연료전지 장기 열화 감지의 기준 기간을 계절을 고려해 다시 설계'),
  BL('발전사 정비·정지 기록을 확보해 이상 후보 알림의 정확도를 실제로 측정'),
  BL('예측 오차를 계통 운영 비용으로 환산하는 가치 기반 평가'),
);

// ── 참고문헌·부록
push(H1('참고문헌'),
  P('[데이터] 공공데이터포털(data.go.kr) 파일데이터 50종을 사용하였다. 자료명·제공기관·포털 번호는 부록 B에 정리하였다. 2025년 일별 전력수급만 전력거래소 전력통계정보시스템(EPSIS) 자료이다.'),
  P('[문헌]'),
  BL('미국 에너지부(DOE), Solar Photovoltaic Performance and Efficiency Basics. https://www.energy.gov/cmei/systems/solar-photovoltaic-performance-and-efficiency-basics'),
  BL('미국 에너지부(DOE), Advanced Drivetrain Manufacturing. https://www.energy.gov/cmei/systems/advanced-drivetrain-manufacturing'),
  BL('NETL, Cost and Performance Baseline for Fossil Energy Plants (2025.5). https://www.osti.gov/servlets/purl/2589925'),
  BL('NREL, Best Research-Cell Efficiency Chart. https://www.nrel.gov/pv/cell-efficiency'),
  BL('한국기계연구원, 「고효율 복합 발전 기술」(2013). https://koreascience.or.kr/article/JAKO201374652240027.pdf'),
  BL('한국중부발전, 「USC 발전설비 국내외 기술동향」(2012). https://koreascience.or.kr/article/JAKO201271433500005.pdf'),
  BL('조선대학교 석사논문, 원전 2차계통 열성능 진단(2016). https://oak.chosun.ac.kr/handle/2020.oak/12938'),
  BL('산업통상자원부, 태양광 연계 ESS REC 가중치 관련 자료. https://www.motir.go.kr/kor/article/ATCLe0854704d/165163/view'),
  BL('아시아경제, "Solar Incentive REC Price Drop Puzzles Industry"(2020.2). https://www.asiae.co.kr/en/article/2020022009575903993'),
  H1('부록 A. 재현 방법'),
  P('코드는 저장소의 energy 폴더에 있다. 데이터 CSV를 energy/data에 UTF-8로 두고 아래 순서로 실행한다.'),
  BL('python fetch_data.py, python fetch_data.py --public → data/ (공공데이터포털에서 50종 내려받기)'),
  BL('python audit.py → results/data_audit.json (데이터 점검)'),
  BL('python analyze.py → results/results.json, figures/*.png (전체 실험, 약 1분)'),
  BL('python analyze_extra.py → LNG 일별 예측, 풍력·소수력 이상 후보 알림'),
  BL('python analyze_public.py, analyze_public2.py, analyze_public3.py → 추가 공공데이터 41종 분석, 그림 f13~f26'),
  P('주요 설정: LightGBM(num_leaves 63, learning_rate 0.05, 검증셋 조기 종료 100회), 학습 2020~2022 / 검증 2023 / 평가 2024, 평가 대상은 낮 시간.'),
  H1('부록 B. 사용한 공공데이터 50종'),
  P('묶음: 기본(처음 받은 자료) · 1차(직접 검색) · 2차·3차(GPT 웹 조사). 파트: ① 지열·수열 ② 화력·원자력·바이오 ③ 태양광·풍력·수력 ④ 종합·모델.'),
  table(['#', '포털 번호', '자료 (제공기관)', '파트', '묶음', '쓴 곳'], CAT.map(c => [c.no, c.pk, `${c.name} (${c.org})`, c.part, c.group, c.use]), [5, 13, 38, 8, 8, 28]),
);

const doc = new Document({
  creator: 'Team', title: '발전원별 AI 예측·관리 시스템 최종보고서',
  styles: {
    default: { document: { run: { font: FONT, size: 21 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: FONT, size: 30, bold: true, color: INK }, paragraph: { spacing: { before: 360, after: 160 }, keepNext: true, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: FONT, size: 24, bold: true, color: TEAL }, paragraph: { spacing: { before: 240, after: 100 }, keepNext: true, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [{ reference: 'bul', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 400, hanging: 260 } } } }] }] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 18, color: '8A96A0' })] })] }) },
    children: body,
  }],
});
Packer.toBuffer(doc).then(buf => { const out = path.join(E, 'report/최종보고서.docx'); fs.writeFileSync(out, buf); console.log('wrote', out); });
