// 발표자료 생성: node deck.js <energy 폴더>
const fs = require('fs'), path = require('path');
const pptxgen = require('pptxgenjs');
const React = require('react'), RDS = require('react-dom/server'), sharp = require('sharp');
const fa = require('react-icons/fa');
let applyTheme = async () => {};                     // pptx 스킬이 없는 환경(Antigravity 등)에서는 테마 적용만 건너뜀
try { if (process.env.SKILL) applyTheme = require(process.env.SKILL + '/scripts/apply_theme.js').applyTheme; } catch (e) { console.warn('apply_theme 없음 — 기본 테마로 저장'); }

const E = process.argv[2];
const R = JSON.parse(fs.readFileSync(path.join(E, 'results/results.json'), 'utf8'));
const A = R.A, B = R.B, Dd = R.D, IV = R.interval, KD = R.kpx_day, FO = R.follow, NU = R.nuclear;
const pct = (x) => (x * 100).toFixed(1), f1 = (x) => Number(x).toFixed(1);

const THEME = { name: 'Grid Teal', headFontFace: 'Malgun Gothic', bodyFontFace: 'Malgun Gothic',
  colors: { dk1: '1D2B36', lt1: 'FFFFFF', dk2: '0B3B3C', lt2: 'EEF4F3', accent1: '0F6E6A', accent2: 'E8A33D',
    accent3: 'C0392B', accent4: '8A96A0', accent5: '5FA8A2', accent6: '2F7D4F', hlink: '0F6E6A', folHlink: '5A6670' } };
const HX = { ink: '1D2B36', dark: '0B3B3C', tint: 'EEF4F3', teal: '0F6E6A', amber: 'E8A33D', red: 'C0392B', muted: '8A96A0', grid: 'D5DEE2' };

const pres = new pptxgen();
pres.layout = 'LAYOUT_16x9';
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = '발전원별 AI 예측·관리 시스템';
const C = pres.SchemeColor;

pres.defineSlideMaster({ title: 'DARK', background: { color: HX.dark },
  objects: [{ placeholder: { options: { name: 'title', type: 'title', x: 0.6, y: 1.55, w: 8.8, h: 1.3, fontSize: 36, bold: true, color: C.background1, valign: 'top', align: 'left', margin: 0 }, text: '' } }] });
pres.defineSlideMaster({ title: 'CONTENT', background: { color: 'FFFFFF' },
  objects: [{ placeholder: { options: { name: 'title', type: 'title', x: 0.5, y: 0.3, w: 9.0, h: 0.65, fontSize: 28, bold: true, color: C.text1, valign: 'middle', align: 'left', margin: 0 }, text: '' } },
    { text: { text: '인공지능과 디지털 사고 · 발전원별 AI 예측·관리 시스템', options: { x: 0.5, y: 5.25, w: 6, h: 0.25, fontSize: 9, color: C.accent4, margin: 0 } } }],
  slideNumber: { x: 9.0, y: 5.22, w: 0.5, h: 0.3, fontSize: 9, color: HX.muted, align: 'right' } });

async function icon(Comp, color, px = 256) {
  const svg = RDS.renderToStaticMarkup(React.createElement(Comp, { color: '#' + color, size: px }));
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return 'image/png;base64,' + buf.toString('base64');
}
const TX = (s, text, o) => s.addText(text, { isTextBox: true, margin: 0, color: C.text1, fontSize: 14, valign: 'top', ...o });
const card = (s, x, y, w, h, fill, name) => s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: fill }, line: { color: fill }, objectName: name });
async function iconDot(s, Comp, x, y, d = 0.5, bg = HX.teal) {
  s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: bg }, line: { color: bg } });
  s.addImage({ data: await icon(Comp, 'FFFFFF'), x: x + d * 0.24, y: y + d * 0.24, w: d * 0.52, h: d * 0.52 });
}
const img = (s, file, x, y, w) => {
  const buf = fs.readFileSync(path.join(E, 'figures', file)); const iw = buf.readUInt32BE(16), ih = buf.readUInt32BE(20);
  const h = w * ih / iw; s.addImage({ path: path.join(E, 'figures', file), x, y, w, h, altText: file }); return h;
};
const CH = { catAxisLabelColor: HX.ink, valAxisLabelColor: HX.muted, catAxisLabelFontFace: '+mn-lt', valAxisLabelFontFace: '+mn-lt',
  dataLabelFontFace: '+mn-lt', catAxisLabelFontSize: 11, valAxisLabelFontSize: 10, dataLabelFontSize: 12, dataLabelColor: HX.ink,
  catGridLine: { style: 'none' }, valGridLine: { style: 'none' }, showLegend: false, titleFontFace: '+mn-lt', valAxisHidden: true, titleFontSize: 12, titleColor: HX.ink, showTitle: true };

(async () => {
  let s;
  // 1 표지
  pres.addSection({ title: '도입' });
  s = pres.addSlide({ masterName: 'DARK', sectionTitle: '도입' });
  s.addText('발전원별 AI 예측·관리 시스템', { placeholder: 'title' });
  TX(s, '공개 데이터로 본 태양광 발전량 예측과 설비 이상탐지', { x: 0.6, y: 2.75, w: 8.8, h: 0.5, fontSize: 18, color: 'CFE3E1' });
  TX(s, '인공지능과 디지털 사고 · 팀 프로젝트   |   2026. 12. 1', { x: 0.6, y: 4.5, w: 8.8, h: 0.35, fontSize: 12, color: 'CFE3E1' });
  TX(s, '팀원: ________  ________  ________  ________', { x: 0.6, y: 4.85, w: 8.8, h: 0.35, fontSize: 12, color: 'CFE3E1' });
  s.addImage({ data: await icon(fa.FaSolarPanel, HX.amber), x: 0.6, y: 0.7, w: 0.6, h: 0.6 });
  s.addNotes('안녕하세요. 저희 팀은 발전원마다 AI가 풀어야 할 문제가 다르다는 관점에서, 공개 데이터로 태양광 발전량을 예측하고 설비 이상을 탐지하는 시스템을 만들었습니다.');

  // 2 70%는 보이지 않는다
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '도입' });
  s.addText(`태양광의 ${(100 - R.metered.share).toFixed(0)}%는 운영자 눈에 보이지 않는다`, { placeholder: 'title' });
  TX(s, `${(100 - R.metered.share).toFixed(0)}%`, { x: 0.5, y: 1.25, w: 3.6, h: 1.2, fontSize: 66, bold: true, color: C.accent1 });
  TX(s, '계량기 없이 추정으로만 아는 태양광 설비 비중', { x: 0.5, y: 2.45, w: 3.6, h: 0.6, fontSize: 14 });
  TX(s, `전국 ${f1(R.metered.total / 1000)}GW 중 계량 설비는 ${f1(R.metered.metered / 1000)}GW뿐. 나머지는 날씨로 "짐작"해야 한다.`, { x: 0.5, y: 3.2, w: 3.6, h: 0.9, fontSize: 13, color: '3C4A55' });
  TX(s, '2024.12.1 발표 공식 태양광 예측 자료 기준', { x: 0.5, y: 4.75, w: 3.6, h: 0.3, fontSize: 10, color: C.accent4 });
  s.addChart(pres.charts.BAR, [{ name: '설비용량(GW)', labels: ['전력구매계약(PPA)', '계량 설비', '자가소비'], values: [R.metered.ppa / 1000, R.metered.metered / 1000, R.metered.btm / 1000].map(v => Number(f1(v))) }],
    { x: 4.5, y: 1.15, w: 5.0, h: 3.7, barDir: 'bar', chartColors: [HX.muted, HX.teal, HX.muted], showValue: true, dataLabelPosition: 'outEnd', dataLabelFormatCode: '0.0"GW"',
      title: '태양광 설비용량 구성', ...CH, catAxisLabelFontSize: 12 });
  s.addNotes(`전국 태양광 ${f1(R.metered.total / 1000)}기가와트 가운데 계량기로 발전량을 바로 보는 설비는 ${f1(R.metered.share)}%뿐입니다. 나머지 약 70%는 날씨를 보고 추정해야 합니다. 그래서 태양광이 늘수록 예측의 중요성이 커집니다.`);

  // 3 발전원 분류
  pres.addSection({ title: '발전과 한계' });
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '발전과 한계' });
  s.addText('누가 출력을 정하는가가 AI의 역할을 정한다', { placeholder: 'title' });
  const H = (x) => ({ text: x, options: { bold: true, color: 'FFFFFF', fill: { color: HX.teal } } });
  const rowsA = [['석탄·LNG 화력', '연료 연소 → 증기·가스터빈', '급전 지시', '가능'], ['원자력', '핵분열 열 → 증기터빈', '정비 일정', '제한적'],
    ['수력·소수력', '낙차 → 수차', '유입량', '가능'], ['지열', '지중 열 → 바이너리 터빈', '지중 온도', '제한적'], ['바이오', '연소·혼소·가스화', '원료 공급', '가능'],
    ['풍력', '양력 → 회전 → 발전기', '풍속', '불가'], ['태양광', '광전효과 → 인버터', '일사량', '불가']];
  s.addTable([[H('발전원'), H('변환 경로'), H('출력을 정하는 것'), H('사람이 제어?')],
    ...rowsA.map(r => r.map((c, i) => ({ text: c, options: (i === 3 && c === '불가') || (i === 2 && ['풍속', '일사량'].includes(c)) ? { bold: true, color: HX.red } : {} })))],
    { x: 0.5, y: 1.15, w: 9.0, colW: [1.9, 3.3, 2.1, 1.7], fontSize: 13, color: HX.ink, border: { type: 'solid', pt: 0.5, color: HX.grid }, rowH: 0.42, valign: 'middle', margin: [0.03, 0.1, 0.03, 0.1] });
  s.addNotes('발전원을 누가 출력을 정하는가로 나눠 보면, 화력은 급전 지시, 원자력은 정비 일정이 출력을 정하지만, 풍력과 태양광은 바람과 햇빛이 정합니다. 사람이 제어할 수 없는 전원이 늘어날수록 예측이 필요해집니다.');

  // 4 기계 기술
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '발전과 한계' });
  s.addText('발전원별 핵심 기계 기술', { placeholder: 'title' });
  const tech = [[fa.FaFire, '가스복합화력', '가스터빈(브레이턴) + 배열회수 증기터빈(랭킨). 터빈 입구 온도가 효율을 좌우'],
    [fa.FaAtom, '원자력', '가압기가 약 150기압 유지 → 약 330℃에서도 냉각재가 끓지 않음. APR1400 설계수명 60년'],
    [fa.FaWind, '풍력', '양력으로 회전, 피치 제어로 과부하 방지. 기어박스 또는 직접구동'],
    [fa.FaSolarPanel, '태양광', '셀 → 직류 → 인버터. 온도가 오르면 효율 하락, 방열·오염 관리 중요'],
    [fa.FaWater, '지열·소수력', '생산정·주입정과 바이너리 터빈 / 낙차·유량에 맞춘 수차'],
    [fa.FaLeaf, '바이오', '전용 보일러, 석탄 혼소, 가스화 후 엔진·터빈']];
  for (let i = 0; i < 6; i++) {
    const x = 0.5 + (i % 3) * 3.05, y = 1.15 + Math.floor(i / 3) * 2.0;
    card(s, x, y, 2.85, 1.8, HX.tint, 'tech' + i);
    await iconDot(s, tech[i][0], x + 0.2, y + 0.2, 0.5);
    TX(s, tech[i][1], { x: x + 0.82, y: y + 0.27, w: 1.9, h: 0.4, fontSize: 15, bold: true, valign: 'middle' });
    TX(s, tech[i][2], { x: x + 0.2, y: y + 0.85, w: 2.5, h: 0.85, fontSize: 11.5, color: '3C4A55' });
  }
  s.addNotes('발전원마다 핵심 기술이 다릅니다. 화력과 원자력은 고온·고압을 견디는 기술, 풍력은 블레이드와 동력 전달, 태양광은 셀과 인버터, 지열과 소수력은 열과 물을 회수하는 설비가 핵심입니다.');

  // 5 물리 법칙의 벽
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '발전과 한계' });
  s.addText('하드웨어는 물리 법칙의 벽에 가까워졌다', { placeholder: 'title' });
  const walls = [['η = 1 − Tc/Th', '카르노 효율', '화력·원자력. 온도를 올리면 효율이 오르지만 소재가 버티지 못한다'],
    ['59.3%', '베츠 한계', '풍력. 바람 에너지를 다 빼앗으면 공기가 터빈 뒤로 흐르지 못한다'],
    ['약 33%', '쇼클리–퀘이서 한계', '단일접합 태양전지. 흡수 못 하는 빛과 열 손실']];
  walls.forEach((w, i) => {
    const x = 0.5 + i * 3.05;
    card(s, x, 1.2, 2.85, 3.3, HX.tint, 'wall' + i);
    TX(s, w[0], { x: x + 0.2, y: 1.45, w: 2.45, h: 0.9, fontSize: i === 0 ? 24 : 40, bold: true, color: C.accent1, valign: 'middle' });
    TX(s, w[1], { x: x + 0.2, y: 2.45, w: 2.45, h: 0.4, fontSize: 15, bold: true });
    TX(s, w[2], { x: x + 0.2, y: 2.95, w: 2.45, h: 1.3, fontSize: 12.5, color: '3C4A55' });
  });
  TX(s, 'AI도 이 벽은 넘지 못한다. AI의 몫은 다른 곳에 있다.', { x: 0.5, y: 4.7, w: 9, h: 0.4, fontSize: 14, italic: true, color: C.accent1 });
  s.addNotes('하드웨어 효율에는 물리 법칙이 정한 상한이 있습니다. 카르노, 베츠, 쇼클리-퀘이서 한계입니다. AI도 이 벽을 넘을 수는 없습니다. 그렇다면 AI는 어디에 쓸 수 있을까요?');

  // 6 한계 4유형
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '발전과 한계' });
  s.addText('한계 네 가지 중 셋은 AI가 줄일 수 있다', { placeholder: 'title' });
  const lim = [['① 열역학 한계', '카르노·베츠·쇼클리–퀘이서', '범위 밖', HX.muted], ['② 간헐성·불확실성', '출력이 날씨에 따라 정해짐', '발전량 예측', HX.teal],
    ['③ 열화·고장', '마모, 출력 저하, 노후화', '이상탐지', HX.teal], ['④ 계통 통합', '화력의 부하 추종 부담', '추종 운전', HX.teal]];
  lim.forEach((l, i) => {
    const y = 1.15 + i * 0.85;
    card(s, 0.5, y, 5.2, 0.7, HX.tint, 'lim' + i);
    TX(s, l[0], { x: 0.7, y: y + 0.08, w: 2.3, h: 0.54, fontSize: 14, bold: true, valign: 'middle' });
    TX(s, l[1], { x: 3.0, y: y + 0.08, w: 2.6, h: 0.54, fontSize: 12, color: '3C4A55', valign: 'middle' });
    s.addShape(pres.shapes.RIGHT_ARROW, { x: 5.85, y: y + 0.2, w: 0.45, h: 0.3, fill: { color: l[3] }, line: { color: l[3] } });
    card(s, 6.45, y, 3.05, 0.7, l[3], 'ai' + i);
    TX(s, l[2], { x: 6.6, y: y + 0.08, w: 2.8, h: 0.54, fontSize: 15, bold: true, color: 'FFFFFF', valign: 'middle' });
  });
  TX(s, '"변동은 없앨 수 없지만, 불확실성은 줄일 수 있다"', { x: 0.5, y: 4.6, w: 9, h: 0.45, fontSize: 16, bold: true, color: C.accent1 });
  s.addNotes('한계를 네 가지로 나누면, 첫째 물리 법칙은 AI도 못 바꿉니다. 하지만 날씨에 따른 불확실성은 예측으로, 열화와 고장은 이상탐지로, 계통 부담은 추종 운전으로 줄일 수 있습니다. 변동 자체는 없앨 수 없지만, 미리 모르는 것은 줄일 수 있습니다.');

  // 7 시스템 설계
  pres.addSection({ title: '시스템과 데이터' });
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '시스템과 데이터' });
  s.addText('발전원마다 다른 문제로 푼다', { placeholder: 'title' });
  const sys = [[fa.FaChartLine, '예측', '태양광 · 풍력 · 수력', '날씨 → 내일 시간별 발전량과 P10~P90 범위', '구현: 태양광 17개 시도'],
    [fa.FaBalanceScale, '추종', '화력 (LNG)', '수요 − 재생에너지를 메우는 운전', '분석: 수요와 LNG 상관'],
    [fa.FaExclamationTriangle, '이상탐지', '연료전지 · 원자력', '정상 출력 패턴에서 벗어나는 날 알림', '구현: 연료전지 5기']];
  for (let i = 0; i < 3; i++) {
    const x = 0.5 + i * 3.05;
    card(s, x, 1.15, 2.85, 3.0, HX.tint, 'sys' + i);
    await iconDot(s, sys[i][0], x + 0.2, 1.35, 0.6, i === 2 ? HX.red : HX.teal);
    TX(s, sys[i][1], { x: x + 0.95, y: 1.38, w: 1.8, h: 0.55, fontSize: 22, bold: true, valign: 'middle' });
    TX(s, sys[i][2], { x: x + 0.2, y: 2.1, w: 2.5, h: 0.35, fontSize: 13, bold: true, color: C.accent1 });
    TX(s, sys[i][3], { x: x + 0.2, y: 2.5, w: 2.5, h: 0.9, fontSize: 12.5, color: '3C4A55' });
    TX(s, sys[i][4], { x: x + 0.2, y: 3.55, w: 2.5, h: 0.4, fontSize: 11.5, italic: true, color: C.accent4 });
  }
  TX(s, '수집 → 점검·보정 → 이용률 변환 → 학습(2020~22) → 검증(2023) → 평가(2024) → 예측구간 보정', { x: 0.5, y: 4.4, w: 9, h: 0.4, fontSize: 12.5 });
  s.addNotes('저희 시스템의 핵심은 모든 발전원에 같은 모델을 쓰지 않는 것입니다. 날씨가 출력을 정하는 태양광은 예측, 화력은 수요를 따라가는 추종, 출력이 일정한 연료전지와 원자력은 정상 패턴에서 벗어나는 것을 잡는 이상탐지로 풀었습니다.');

  // 8 데이터 점검
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '시스템과 데이터' });
  s.addText('공공데이터 10종, 그대로 쓸 수 없었다', { placeholder: 'title' });
  TX(s, '7건', { x: 0.5, y: 1.2, w: 2.6, h: 1.0, fontSize: 60, bold: true, color: C.accent3 });
  TX(s, '학습 전에 찾아 바로잡은 데이터 문제', { x: 0.5, y: 2.25, w: 2.6, h: 0.7, fontSize: 14 });
  TX(s, '태양광 시간별 80만 행, 발전설비 46곳 일별, 수요·화력·원전·수급 자료', { x: 0.5, y: 3.1, w: 2.6, h: 0.9, fontSize: 12, color: '3C4A55' });
  const issues = [['중복 행 66,976개', '같은 지역·시각이 두 번, 값도 서로 다름'], ['해 진 뒤 발전량', `2021년 전체의 ${R.night_share_total['2021']}% — ESS 방전 추정`],
    ['단위 1,000배 오류', '중부발전 2025년 1~6월만 다른 단위'], ['설비용량 절반 표기', '인천연료전지 이용률이 1.8로 계산됨'],
    ['열 이름 밀림', '2025 수급 파일, 식으로 검증해 바로잡음'], ['시각 기준 어긋남', '저녁 관측 일사량 > 계산값 27,566건'], ['두 파일 값 차이', '신한울 시운전 발전량 포함 여부']];
  issues.forEach((it, i) => {
    const y = 1.15 + i * 0.52;
    card(s, 3.4, y, 6.1, 0.44, HX.tint, 'issue' + i);
    TX(s, it[0], { x: 3.55, y: y + 0.05, w: 2.3, h: 0.34, fontSize: 12.5, bold: true, valign: 'middle' });
    TX(s, it[1], { x: 5.85, y: y + 0.05, w: 3.55, h: 0.34, fontSize: 11.5, color: '3C4A55', valign: 'middle' });
  });
  s.addNotes('데이터를 받아 바로 쓰지 않고 먼저 점검했습니다. 중복 행 6만 7천 개, 특정 기간만 단위가 1000배 큰 오류, 열 이름이 한 칸 밀린 파일 등 7건을 찾아 바로잡았습니다. 이 과정을 거치지 않았다면 모델이 엉뚱한 것을 배웠을 겁니다.');

  // 9 야간 발전
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '시스템과 데이터' });
  s.addText('해가 진 뒤의 "태양광" 발전량', { placeholder: 'title' });
  img(s, 'f6_night.png', 0.5, 1.1, 5.3);
  TX(s, `${R.night_share_total['2021']}% → ${R.night_share_total['2024']}%`, { x: 6.1, y: 1.2, w: 3.4, h: 0.8, fontSize: 30, bold: true, color: C.accent1 });
  TX(s, '해가 없는 시간에 기록된 발전량 비중 (전국, 2021 → 2024)', { x: 6.1, y: 2.0, w: 3.4, h: 0.6, fontSize: 12 });
  TX(s, [{ text: '추정 원인: 태양광 연계 ESS 방전', options: { bold: true, breakLine: true } },
    { text: '낮에 충전해 16시 이후 방전하면 높은 REC 가중치를 받았고, 이 가중치가 2020년 하반기 낮아진 뒤 폐지됨. 데이터 추세와 시기가 맞음', options: {} }],
    { x: 6.1, y: 2.75, w: 3.4, h: 1.7, fontSize: 12, color: '3C4A55' });
  TX(s, '데이터에 ESS 표시가 없어 확정은 못 함', { x: 6.1, y: 4.55, w: 3.4, h: 0.3, fontSize: 10.5, italic: true, color: C.accent4 });
  s.addNotes(`흥미로운 점이 있었습니다. 태양광 데이터인데 해가 진 뒤에도 발전량이 찍혀 있었습니다. 연도별로 보면 2021년 ${R.night_share_total['2021']}%에서 2024년 ${R.night_share_total['2024']}%로 줄었는데, 태양광 연계 ESS 방전에 대한 REC 가중치가 축소·폐지된 시기와 맞습니다. 다만 데이터에 ESS 표시가 없어 추정으로 말씀드립니다.`);

  // 10 결과 A
  pres.addSection({ title: '예측 결과' });
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '예측 결과' });
  s.addText(`AI 예측은 "어제 값"보다 오차가 ${(A.LightGBM.Skill * 100).toFixed(0)}% 작다`, { placeholder: 'title' });
  s.addChart(pres.charts.BAR, [{ name: 'nRMSE', labels: ['LightGBM', '선형회귀', '어제 같은 시각'], values: [A.LightGBM.nRMSE, A['선형회귀'].nRMSE, A.Persistence.nRMSE].map(v => Number(f1(v))) }],
    { x: 0.5, y: 1.15, w: 5.6, h: 3.6, barDir: 'bar', chartColors: [HX.teal, HX.muted, HX.muted], showValue: true, dataLabelPosition: 'outEnd', dataLabelFormatCode: '0.0"%"',
      title: 'nRMSE — 설비용량 대비 오차 (2024년 낮 시간)', ...CH, catAxisLabelFontSize: 12 });
  card(s, 6.4, 1.15, 3.1, 3.6, HX.tint, 'skillcard');
  TX(s, A.LightGBM.Skill.toFixed(2), { x: 6.6, y: 1.35, w: 2.7, h: 1.0, fontSize: 54, bold: true, color: C.accent1 });
  TX(s, 'Skill Score', { x: 6.6, y: 2.35, w: 2.7, h: 0.35, fontSize: 15, bold: true });
  TX(s, '1 − 모델 오차 ÷ 어제 값 오차. 0이면 어제 값과 같고 1에 가까울수록 좋다', { x: 6.6, y: 2.75, w: 2.7, h: 0.9, fontSize: 11.5, color: '3C4A55' });
  TX(s, `17개 시도 · 2024년 평가 · 3회 반복 표준편차 ±${A.LightGBM.nRMSE_std.toFixed(2)}%p`, { x: 6.6, y: 3.85, w: 2.7, h: 0.7, fontSize: 10.5, color: C.accent4 });
  s.addNotes(`결과입니다. 2020년부터 2022년까지 학습하고 2024년으로 평가했습니다. 어제 같은 시각과 같다고 보는 기준선의 오차는 설비용량의 ${f1(A.Persistence.nRMSE)}%인데, LightGBM은 ${f1(A.LightGBM.nRMSE)}%로 오차를 ${(A.LightGBM.Skill * 100).toFixed(0)}% 줄였습니다. 밤의 0을 맞히는 착시를 막으려고 낮 시간만 평가했습니다.`);

  // 11 날씨 정보
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '예측 결과' });
  s.addText('성능의 대부분은 날씨 정보에서 나온다', { placeholder: 'title' });
  const bv = Object.values(B).map(v => Number(f1(v.nRMSE)));
  s.addChart(pres.charts.BAR, [{ name: 'nRMSE', labels: ['날씨 정보 없음', '예보 항목', '+ 실측 일사량'], values: bv }],
    { x: 0.5, y: 1.15, w: 4.8, h: 3.6, barDir: 'col', chartColors: [HX.muted, HX.teal, HX.amber], showValue: true, dataLabelPosition: 'outEnd', dataLabelFormatCode: '0.0"%"',
      title: '입력 날씨 정보에 따른 nRMSE', ...CH, catAxisLabelFontSize: 11.5 });
  card(s, 5.6, 1.15, 3.9, 3.6, 'FDF3E3', 'caveat');
  TX(s, '정직하게 말하면', { x: 5.8, y: 1.3, w: 3.5, h: 0.4, fontSize: 15, bold: true, color: 'A86A12' });
  TX(s, [{ text: '실험의 날씨는 예보가 아니라 실제 관측값이다. 결과는 "예보가 완벽하다면"의 상한선.', options: { breakLine: true } },
    { text: ' ', options: { breakLine: true, fontSize: 6 } },
    { text: '2024.12.2 하루 비교 (nRMSE)', options: { bold: true, breakLine: true } },
    { text: `공식 하루 전 예측 ${f1(KD['공식 하루 전 예측'].nRMSE)}% · 어제 값 ${f1(KD.Persistence.nRMSE)}% · 우리 모델 ${f1(KD['우리 모델(관측 기상 입력)'].nRMSE)}%`, options: { breakLine: true } },
    { text: ' ', options: { breakLine: true, fontSize: 6 } },
    { text: '이 격차가 곧 "예보 날씨 vs 실제 날씨"의 차이 → 병목은 모델보다 기상 예보', options: { bold: true } }],
    { x: 5.8, y: 1.75, w: 3.5, h: 2.9, fontSize: 12, color: '3C4A55' });
  s.addNotes(`날씨 정보 없이 예측하면 오차가 ${f1(bv[0])}%로 어제 값과 큰 차이가 없습니다. 기온, 운량 같은 예보 항목을 넣으면 ${f1(bv[1])}%로 떨어집니다. 다만 정직하게 말씀드리면 실험의 날씨는 실제 관측값이라 상한선입니다. 공식 하루 전 예측과 하루 비교해 보면 그 격차가 보이고, 결국 병목은 모델보다 기상 예보의 정확도입니다.`);

  // 12 정규화
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '예측 결과' });
  s.addText('설비가 두 배로 늘어도 흔들리지 않게', { placeholder: 'title' });
  s.addChart(pres.charts.BAR, [{ name: 'GW', labels: ['2020', '2021', '2022', '2023', '2024'], values: Dd.cap_total.map(v => Number(f1(v / 1000))) }],
    { x: 0.5, y: 1.15, w: 4.6, h: 3.4, barDir: 'col', chartColors: [HX.teal], showValue: true, dataLabelPosition: 'outEnd', dataLabelFormatCode: '0.0',
      title: '데이터 속 계량 태양광 설비용량 (GW)', ...CH });
  const bi = [[`${f1(Dd['원시 발전량(MWh) 학습'].bias)}%p`, '발전량(MWh) 그대로 학습', '과거 설비 규모로 예측 → 2024년을 체계적으로 낮게', HX.red],
    [`+${f1(Dd['이용률(CF) 학습'].bias)}%p`, '이용률(발전량 ÷ 설비용량)로 학습', '날씨만 배우고, 예측 후 설비용량을 다시 곱함', HX.teal]];
  bi.forEach((v, i) => {
    const y = 1.15 + i * 1.75;
    card(s, 5.4, y, 4.1, 1.6, HX.tint, 'bias' + i);
    TX(s, v[0], { x: 5.6, y: y + 0.15, w: 1.6, h: 0.7, fontSize: 28, bold: true, color: v[3], valign: 'middle' });
    TX(s, v[1], { x: 7.2, y: y + 0.18, w: 2.2, h: 0.65, fontSize: 13, bold: true, valign: 'middle' });
    TX(s, v[2], { x: 5.6, y: y + 0.9, w: 3.8, h: 0.6, fontSize: 11.5, color: '3C4A55' });
  });
  TX(s, '2024년 예측 치우침 (설비용량 대비)', { x: 5.4, y: 4.6, w: 4.1, h: 0.3, fontSize: 10.5, color: C.accent4 });
  s.addNotes(`데이터 속 설비는 4년 만에 ${f1(Dd.cap_total[0] / 1000)}기가와트에서 ${f1(Dd.cap_total[4] / 1000)}기가와트로 두 배가 넘게 늘었습니다. 발전량을 그대로 학습하면 AI가 날씨가 아니라 과거 설비 규모를 배워서 2024년을 약 ${Math.abs(Dd['원시 발전량(MWh) 학습'].bias).toFixed(0)}%포인트 낮게 예측합니다. 설비용량으로 나눈 이용률로 학습하면 이 치우침이 사라집니다.`);

  // 13 맞은 날 틀린 날
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '예측 결과' });
  s.addText('잘 맞은 날, 크게 틀린 날', { placeholder: 'title' });
  img(s, 'f3_days.png', 0.5, 1.05, 9.0);
  TX(s, [{ text: `P10~P90 범위가 실제값의 ${pct(IV.calibrated_coverage)}%를 포함`, options: { bold: true, color: HX.teal } },
    { text: `  (보정 전 ${pct(IV.raw_coverage)}% → conformal 보정으로 목표 80%에 맞춤)  ·  틀린 날이 있다는 것 자체가 "불확실성은 줄일 뿐 없앨 수 없다"는 근거`, options: {} }],
    { x: 0.5, y: 4.4, w: 9.0, h: 0.6, fontSize: 12, color: '3C4A55' });
  s.addNotes(`왼쪽 맑은 날은 예측이 실제를 잘 따라갑니다. 오른쪽 ${R.fig_days.worst}에는 예상보다 맑은 오후가 와서 크게 낮게 예측했습니다. 그래서 저희는 값 하나가 아니라 P10에서 P90 범위를 함께 보여주고, 실제값의 80%가 이 범위에 들어오도록 보정했습니다. 저녁에 남은 실제 발전량은 앞에서 말씀드린 ESS 방전으로 보입니다.`);

  // 14 이상탐지
  pres.addSection({ title: '이상탐지와 추종' });
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '이상탐지와 추종' });
  s.addText('예측할 게 없는 설비는 "평소와 다름"을 잡는다', { placeholder: 'title' });
  img(s, 'f8_fuelcell.png', 0.5, 1.05, 6.0);
  const fcAll = Object.values(R.fuelcell);
  TX(s, `${fcAll.reduce((a, v) => a + v.events, 0)}건`, { x: 6.8, y: 1.1, w: 2.7, h: 0.75, fontSize: 36, bold: true, color: C.accent3 });
  TX(s, '연료전지 5기에서 잡힌 출력 급락 구간 (2023.11~2026.8)', { x: 6.8, y: 1.85, w: 2.7, h: 0.6, fontSize: 12 });
  TX(s, '기준: 과거 28일 중앙값보다 통계적으로 크게 낮고(3σ) 설비용량의 15%p 이상 하락', { x: 6.8, y: 2.55, w: 2.7, h: 0.9, fontSize: 11, color: '3C4A55' });
  TX(s, [{ text: `태양광 발전소 ${R.solar_peer.plants}곳`, options: { bold: true, breakLine: true } }, { text: `같은 날 같은 지역 발전소와 비교 → 날씨 영향 제거, 저하 후보 ${R.solar_peer.events}구간`, options: {} }],
    { x: 6.8, y: 3.55, w: 2.7, h: 1.0, fontSize: 11, color: '3C4A55' });
  TX(s, '정비 기록과 대조하지 못해 실제 고장 여부는 미검증', { x: 0.5, y: 4.7, w: 6, h: 0.3, fontSize: 10.5, italic: true, color: C.accent4 });
  s.addNotes('연료전지는 날씨와 상관없이 출력이 거의 일정해서 예측할 것이 없습니다. 대신 과거 28일의 정상 패턴보다 크게 떨어진 날을 잡았습니다. 처음에는 통계 기준만 써서 알림이 너무 많았는데, 15%포인트 이상 하락이라는 실무 기준을 더하자 의미 있는 급락만 남았습니다. 세종연료전지는 2026년 4월 정지와 함께 장기적인 출력 저하도 보입니다.');

  // 15 화력 추종 + 원자력
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '이상탐지와 추종' });
  s.addText('LNG는 수요를 따라가고, 원전은 노후화를 살핀다', { placeholder: 'title' });
  s.addChart(pres.charts.BAR, [{ name: '상관계수', labels: ['LNG', '석탄', '유류'], values: [FO.corr.LNG, FO.corr['석탄'], FO.corr['유류']] }],
    { x: 0.5, y: 1.15, w: 4.3, h: 2.6, barDir: 'col', chartColors: [HX.teal, HX.muted, HX.muted], showValue: true, dataLabelPosition: 'outEnd', dataLabelFormatCode: '0.00',
      title: '하루 전력수요와의 상관계수 (2018~2021)', valAxisMaxVal: 1, valAxisMinVal: 0, ...CH });
  TX(s, `LNG 출력 변동은 수요의 ${(FO.cv.LNG / FO.cv.demand_GWh).toFixed(1)}배 → 수요와 재생에너지의 변동을 메우는 "추종" 전원. 태양광 예측이 정확할수록 준비량이 준다`, { x: 0.5, y: 3.9, w: 4.3, h: 0.9, fontSize: 12, color: '3C4A55' });
  img(s, 'f10_nuclear.png', 5.1, 1.15, 4.4);
  TX(s, `한빛 5호기 연간 이용률 2021년 ${f1(NU.hanbit5['2021'])}%, 2023년 ${f1(NU.hanbit5['2023'])}%. 운영 원전 ${NU.operating_units}기 중 ${NU.expire_by_2030.length}기가 2030년까지 설계수명 만료 → 상태 감시 수요 증가`, { x: 5.1, y: 3.3, w: 4.4, h: 1.0, fontSize: 12, color: '3C4A55' });
  s.addNotes(`화력은 하루 전력수요와의 상관이 LNG ${FO.corr.LNG}, 석탄 ${FO.corr['석탄']}으로, LNG가 수요를 따라가는 추종 역할을 합니다. 원자력은 한빛 5호기의 이용률이 크게 떨어진 해들이 보이고, 2030년까지 ${NU.expire_by_2030.length}기가 설계수명을 맞기 때문에 상태 감시의 필요성이 커집니다.`);

  // 15-1 LNG 일별 예측 (analyze_extra.py 결과가 있을 때만)
  const LP = R.lng_pred;
  if (LP) {
    const M = LP.models, kU = '선형회귀 · 관측 수요 입력(사후 참고)', kR = '선형회귀 · 전날 수요만 입력(현실 조건)', kP = '어제 값(Persistence)';
    s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '이상탐지와 추종' });
    s.addText('LNG 발전량은 하루 단위로 예측할 수 있다', { placeholder: 'title' });
    img(s, 'f11_lng_pred.png', 0.5, 1.05, 6.0);
    s.addChart(pres.charts.BAR, [{ name: 'nRMSE', labels: ['어제 값', '전날 수요만', '당일 관측 수요'], values: [M[kP].nRMSE, M[kR].nRMSE, M[kU].nRMSE] }],
      { x: 6.7, y: 1.05, w: 2.9, h: 2.4, barDir: 'bar', chartColors: [HX.muted, HX.amber, HX.teal], showValue: true, dataLabelPosition: 'outEnd', dataLabelFormatCode: '0.0"%"',
        title: `nRMSE (${LP.test}년 시험, 선형회귀)`, ...CH });
    TX(s, `전날까지 정보로 Skill ${M[kR].Skill.toFixed(2)} (어제 값 대비 오차 ${(M[kR].Skill * 100).toFixed(0)}% 감소). 수요를 빼도 ${M['선형회귀 · 수요 없음(달력+과거 LNG)'].Skill.toFixed(2)}로 비슷 → 최근 LNG 패턴과 요일이 대부분을 설명. 당일 실제 수요(사후 참고)는 ${M[kU].Skill.toFixed(2)}`, { x: 6.7, y: 3.55, w: 2.9, h: 1.1, fontSize: 11, color: '3C4A55' });
    TX(s, `학습 ${LP.train} · 시험 ${LP.test} (${LP.test_days}일) · nRMSE는 일평균 LNG ${f1(LP.test_mean_GWh)} GWh 대비`, { x: 0.5, y: 4.7, w: 6, h: 0.3, fontSize: 10.5, italic: true, color: C.accent4 });
    s.addNotes(`LNG 발전량을 하루 단위로 예측했습니다. 기준은 어제 값을 그대로 쓰는 방법입니다. 당일 실제 전력수요를 넣으면 오차가 어제 값보다 ${(M[kU].Skill * 100).toFixed(0)}% 줄지만, 하루가 끝나야 알 수 있는 수요를 쓴 사후 참고 결과입니다. 전날 수요만 쓰는 현실 조건에서는 ${(M[kR].Skill * 100).toFixed(0)}% 줄었습니다.`);
  }
  // 15-2 풍력·소수력 이상 후보 알림
  const WH = R.wind_hydro;
  if (WH) {
    s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '이상탐지와 추종' });
    s.addText('같은 규칙도 발전원마다 다르게 작동한다', { placeholder: 'title' });
    img(s, 'f12_wind_hydro.png', 0.5, 1.05, 6.0);
    TX(s, [{ text: '두 규칙 비교: ① 연료전지 규칙(28일 중앙값 대비 3σ + 15%p 하락) ② 상대 하락 규칙(3σ + 기준의 50% 이상 하락)', options: { breakLine: true } },
      { text: ' ', options: { breakLine: true } },
      { text: '풍력: 두 규칙 모두 0건 — 바람에 따라 매일 크게 출렁여 발전량만으로는 "튀는 날"이 드러나지 않음. 바람 데이터가 필요. 양양풍력(기록 1일)은 판정 불가', options: { bullet: true, breakLine: true } },
      { text: '소수력: 강수·유량과 대조 전에는 갈수기와 설비 문제를 구분할 수 없음. 신서천(기록 대부분 0)은 판단 보류', options: { bullet: true } }],
      { x: 6.7, y: 1.1, w: 2.9, h: 3.4, fontSize: 11, color: '3C4A55' });
    TX(s, '이상 후보 알림 — 정비 기록과 대조하지 않음', { x: 0.5, y: 4.7, w: 6, h: 0.3, fontSize: 10.5, italic: true, color: C.accent4 });
    s.addNotes('연료전지에 쓴 규칙과 평소의 절반 이상 떨어진 날을 잡는 비율 규칙을 풍력과 소수력에 적용했습니다. 제주상명풍력은 두 규칙 모두 0건이었는데, 이상이 없다는 뜻이 아니라 바람 때문에 매일 크게 출렁여 발전량만으로는 가려내기 어렵다는 뜻입니다. 소수력은 강수·유량 기록과 대조해야 갈수기와 설비 문제를 구분할 수 있습니다.');
  }

  // 16 결론
  pres.addSection({ title: '결론' });
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '결론' });
  s.addText('AI가 할 수 있는 것과 없는 것', { placeholder: 'title' });
  card(s, 0.5, 1.15, 4.4, 3.0, HX.tint, 'can');
  await iconDot(s, fa.FaCheck, 0.7, 1.32, 0.45);
  TX(s, '할 수 있는 것', { x: 1.3, y: 1.35, w: 3.4, h: 0.4, fontSize: 16, bold: true, valign: 'middle' });
  TX(s, [{ text: `태양광 예측 오차 ${(A.LightGBM.Skill * 100).toFixed(0)}% 감소 (기준선 대비)`, options: { bullet: true, breakLine: true } },
    { text: '불확실성을 범위(P10~P90)로 알려줌', options: { bullet: true, breakLine: true } },
    { text: '설비 증설에도 흔들리지 않는 학습', options: { bullet: true, breakLine: true } },
    { text: '고장·출력 저하 신호를 일찍 포착', options: { bullet: true } }], { x: 0.7, y: 1.95, w: 4.0, h: 2.1, fontSize: 13, paraSpaceAfter: 6 });
  card(s, 5.1, 1.15, 4.4, 3.0, 'FBECEA', 'cannot');
  await iconDot(s, fa.FaTimes, 5.3, 1.32, 0.45, HX.red);
  TX(s, '할 수 없는 것 · 남은 한계', { x: 5.9, y: 1.35, w: 3.5, h: 0.4, fontSize: 16, bold: true, valign: 'middle' });
  TX(s, [{ text: '카르노·베츠·쇼클리–퀘이서 한계', options: { bullet: true, breakLine: true } },
    { text: '실험 날씨가 관측값 → 실제 성능은 더 낮음', options: { bullet: true, breakLine: true } },
    { text: '시도 합계·계량 설비(29%)만 학습', options: { bullet: true, breakLine: true } },
    { text: '이상 알림을 정비 기록과 대조 못 함', options: { bullet: true } }], { x: 5.3, y: 1.95, w: 4.0, h: 2.1, fontSize: 13, paraSpaceAfter: 6 });
  TX(s, '다음 단계: 과거 기상 예보로 실제 성능 측정 · ESS 분리 · 발전소 단위 확장 · 오차의 비용 환산', { x: 0.5, y: 4.4, w: 9, h: 0.5, fontSize: 12.5, color: C.accent1, bold: true });
  s.addNotes('정리하겠습니다. AI는 물리 법칙의 한계를 넘지 못합니다. 하지만 이미 있는 설비가 언제, 얼마나 전기를 만들지 미리 알려주고, 고장 신호를 일찍 잡아 설비를 더 짓지 않고도 손실을 줄일 수 있습니다. 실험 날씨가 관측값이라는 한계가 있어, 다음 단계로 과거 기상 예보로 실제 성능을 재 보는 것을 제안합니다.');

  // 17 마무리
  s = pres.addSlide({ masterName: 'DARK', sectionTitle: '결론' });
  s.addText('설비를 더 짓기 전에, 이미 있는 설비를 더 잘 알자', { placeholder: 'title' });
  TX(s, '감사합니다 · 질문 받겠습니다', { x: 0.6, y: 3.0, w: 8.8, h: 0.5, fontSize: 18, color: 'CFE3E1' });
  TX(s, '데이터: 공공데이터포털 — 시도별 시간별 태양광 학습데이터(2020~2024), 공식 태양광 예측(2024.12.2), 한국중부발전 설비별 일별 발전량, 시간별 전력수요, 연료원별 화력 발전량, 원전 호기별 발전량·이용률, 2025 전력수급   ·   코드: energy/analyze.py',
    { x: 0.6, y: 4.3, w: 8.8, h: 0.8, fontSize: 10, color: 'A9C9C6' });
  s.addNotes('발표를 마치겠습니다. 감사합니다.');

  const out = path.join(E, 'report/발표자료.pptx');
  await pres.writeFile({ fileName: out });
  await applyTheme(out, THEME);
  console.log('wrote', out);
})();
