// 최종 발표자료(발표 4개 파트 순서) + 발표대본 자동 생성
// 실행: SKILL=<pptx 스킬 경로> node build/deck_final.js <energy 폴더>
// 출력: report/발표자료_최종.pptx, report/발표대본.md (대본 = 슬라이드 발표자 노트)
const fs = require('fs'), path = require('path');
const pptxgen = require('pptxgenjs');
const React = require('react'), RDS = require('react-dom/server'), sharp = require('sharp');
const fa = require('react-icons/fa');
let applyTheme = async () => {};
try { if (process.env.SKILL) applyTheme = require(process.env.SKILL + '/scripts/apply_theme.js').applyTheme; } catch (e) { console.warn('apply_theme 없음 — 기본 테마로 저장'); }

const E = process.argv[2];
const R = JSON.parse(fs.readFileSync(path.join(E, 'results/results.json'), 'utf8'));
const A = R.A, D = R.D, IV = R.interval, KD = R.kpx_day, FO = R.follow, NU = R.nuclear, M = R.metered;
const LM = R.lng_pred.models, LP = R.lng_pred, WH = R.wind_hydro.plants, SI = R.solar_issue_14, SII = R.solar_interval_issue_14, CU = R.fuelcell_cusum.plants;
const P1 = R.public, P2 = R.public2, P3 = R.public3, PL = R.plan;
const kR = '선형회귀 · 전날 수요만 입력(현실 조건)', kU = '선형회귀 · 관측 수요 입력(사후 참고)', kN = '선형회귀 · 수요 없음(달력+과거 LNG)', kP = '어제 값(Persistence)';
const f1 = (x) => Number(x).toFixed(1), f2 = (x) => Number(x).toFixed(2), pct0 = (x) => (x * 100).toFixed(0), num = (x) => Number(x).toLocaleString('ko-KR');
const sum = (o) => Object.values(o).reduce((a, v) => a + v, 0);

const THEME = { name: 'Grid Teal', headFontFace: 'Malgun Gothic', bodyFontFace: 'Malgun Gothic',
  colors: { dk1: '1D2B36', lt1: 'FFFFFF', dk2: '0B3B3C', lt2: 'EEF4F3', accent1: '0F6E6A', accent2: 'E8A33D',
    accent3: 'C0392B', accent4: '8A96A0', accent5: '5FA8A2', accent6: '2F7D4F', hlink: '0F6E6A', folHlink: '5A6670' } };
const HX = { ink: '1D2B36', dark: '0B3B3C', tint: 'EEF4F3', teal: '0F6E6A', amber: 'E8A33D', red: 'C0392B', muted: '8A96A0', grid: 'D5DEE2', sub: '3C4A55' };
const PART = { 1: ['①', '지열·수열', '7A5C99'], 2: ['②', '화력·원자력·바이오', 'A44A3F'], 3: ['③', '태양광·풍력·수력', '2E7D4F'], 4: ['④', '종합 및 모델 생성', '2D5F8A'] };

const pres = new pptxgen();
pres.layout = 'LAYOUT_16x9';
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = '발전원별 AI 예측·관리 시스템';
const C = pres.SchemeColor;
pres.defineSlideMaster({ title: 'DARK', background: { color: HX.dark },
  objects: [{ placeholder: { options: { name: 'title', type: 'title', x: 0.6, y: 1.45, w: 8.8, h: 1.4, fontSize: 34, bold: true, color: C.background1, valign: 'top', align: 'left', margin: 0 }, text: '' } }] });
pres.defineSlideMaster({ title: 'CONTENT', background: { color: 'FFFFFF' },
  objects: [{ placeholder: { options: { name: 'title', type: 'title', x: 0.5, y: 0.32, w: 7.0, h: 0.6, fontSize: 22, bold: true, color: C.text1, valign: 'middle', align: 'left', margin: 0 }, text: '' } },
    { text: { text: '인공지능과 디지털 사고 · 발전원별 AI 예측·관리 시스템', options: { x: 0.5, y: 5.27, w: 6, h: 0.22, fontSize: 8.5, color: C.accent4, margin: 0 } } }],
  slideNumber: { x: 9.0, y: 5.22, w: 0.5, h: 0.3, fontSize: 9, color: HX.muted, align: 'right' } });

async function icon(Comp, color, px = 256) {
  const svg = RDS.renderToStaticMarkup(React.createElement(Comp, { color: '#' + color, size: px }));
  return 'image/png;base64,' + (await sharp(Buffer.from(svg)).png().toBuffer()).toString('base64');
}
const TX = (s, text, o) => s.addText(text, { isTextBox: true, margin: 0, color: C.text1, fontSize: 13, valign: 'top', paraSpaceAfter: 4, ...o });
const SRC = (s, text) => TX(s, text, { x: 0.5, y: 4.93, w: 8.4, h: 0.28, fontSize: 8.5, italic: true, color: C.accent4 });
function img(s, file, x, y, w, hmax = 9) {           // 너비 w, 높이 hmax 안에 비율 유지
  const p = path.join(E, 'figures', file), buf = fs.readFileSync(p); const iw = buf.readUInt32BE(16), ih = buf.readUInt32BE(20);
  let ww = w, hh = w * ih / iw; if (hh > hmax) { hh = hmax; ww = hh * iw / ih; }
  s.addImage({ path: p, x, y, w: ww, h: hh, altText: file }); return { w: ww, h: hh };
}
const bl = (items) => items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1 } }));
function card(s, x, y, w, h, big, label, color = HX.teal) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.06, fill: { color: HX.tint }, line: { color: HX.tint } });
  TX(s, big, { x: x + 0.15, y: y + 0.1, w: w - 0.3, h: 0.5, fontSize: 22, bold: true, color });
  TX(s, label, { x: x + 0.15, y: y + 0.62, w: w - 0.3, h: h - 0.7, fontSize: 10.5, color: HX.sub });
}

// 대본 모으기: 슬라이드 노트 = 대본
const SCRIPT = []; let slideNo = 0;
function slide(title, part, master = 'CONTENT') {
  const s = pres.addSlide({ masterName: master, sectionTitle: part ? PART[part][1] : '도입' }); slideNo++;
  if (title) s.addText(title, { placeholder: 'title' });
  if (part && master === 'CONTENT') {
    const [m, nm, col] = PART[part];
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 7.6, y: 0.42, w: 1.9, h: 0.34, rectRadius: 0.08, fill: { color: col }, line: { color: col } });
    TX(s, `${m} ${nm}`, { x: 7.6, y: 0.42, w: 1.9, h: 0.34, fontSize: 9, bold: true, color: 'FFFFFF', align: 'center', valign: 'middle' });
  }
  s._meta = { title, part, no: slideNo }; return s;
}
function note(s, text) { s.addNotes(text); SCRIPT.push({ ...s._meta, text }); }

(async () => {
  let s;
  // ───── 표지·목차 ─────
  pres.addSection({ title: '도입' });
  s = slide('발전원별 AI 예측·관리 시스템', 0, 'DARK');
  TX(s, '수요에 맞춰 계획하고, 발전량을 예측해 효율적으로 생산하기', { x: 0.6, y: 2.75, w: 8.8, h: 0.5, fontSize: 17, color: 'CFE3E1' });
  TX(s, '인공지능과 디지털 사고 · 팀 프로젝트   |   2026. 12. 1', { x: 0.6, y: 4.45, w: 8.8, h: 0.35, fontSize: 12, color: 'CFE3E1' });
  TX(s, '팀원: ________  ________  ________  ________', { x: 0.6, y: 4.82, w: 8.8, h: 0.35, fontSize: 12, color: 'CFE3E1' });
  s.addImage({ data: await icon(fa.FaSolarPanel, HX.amber), x: 0.6, y: 0.65, w: 0.55, h: 0.55 });
  note(s, '안녕하세요. 저희 목표는 사람들이 전기를 얼마나 쓸지(수요)를 미리 알고, 그에 맞춰 발전 계획을 세우고, 발전소마다 얼마나 만들지 예측해서 에너지를 낭비 없이 생산하는 것입니다. "설비를 더 짓기 전에, 이미 있는 설비를 더 잘 알자"는 생각으로, 공공데이터 50종을 써서 발전소 종류마다 AI가 어떤 일을 할 수 있는지 확인했습니다.');

  s = slide('오늘의 순서', 0);
  const rows = [[1, '지열·수열', '지열 히트펌프 운전 기록으로 "평소와 다른 날" 찾기'], [2, '화력·원자력·바이오', 'LNG 수요 추종과 일별 예측, 원전 정비와 이용률, 바이오 연료'],
    [3, '태양광·풍력·수력', '태양광 하루 전 예측과 그 조건, 풍속을 함께 본 풍력'], [4, '종합 및 모델 생성', '수요에 맞춘 발전 계획 AI, 데이터 점검부터 학습·평가까지, 그리고 한계']];
  rows.forEach(([k, nm, d], i) => {
    const y = 1.15 + i * 0.9, col = PART[k][2];
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y, w: 0.7, h: 0.7, rectRadius: 0.1, fill: { color: col }, line: { color: col } });
    TX(s, PART[k][0], { x: 0.5, y, w: 0.7, h: 0.7, fontSize: 24, bold: true, color: 'FFFFFF', align: 'center', valign: 'middle' });
    TX(s, nm, { x: 1.4, y: y + 0.02, w: 3.0, h: 0.35, fontSize: 16, bold: true });
    TX(s, d, { x: 1.4, y: y + 0.38, w: 8.0, h: 0.3, fontSize: 11.5, color: HX.sub });
  });
  note(s, '발표는 네 파트로 나눠 진행합니다. 지열·수열, 화력·원자력·바이오, 태양광·풍력·수력을 차례로 보고, 마지막 파트에서 수요에 맞춘 발전 계획 AI와 전체 과정, 한계를 정리하겠습니다.');

  s = slide('알아 둘 말 다섯 가지', 0);
  const GL = [['이용률', '발전소가 낼 수 있는 최대 전기 중 실제로 낸 비율. 100 MW 설비가 1시간에 30 MWh를 만들면 30%'],
    ['오차(%)', '예측이 실제와 평균적으로 얼마나 어긋났는지. 낮을수록 좋다. 비교 기준은 "어제(지난주) 값을 그대로 쓰기"'],
    ['상관계수', '두 값이 함께 움직이는 정도. 1에 가까우면 같이 오르내리고, -1에 가까우면 반대로, 0이면 관계가 거의 없다'],
    ['이상 후보 알림', '평소보다 출력이 크게 떨어진 날을 표시하는 것. 실제 고장인지는 정비 기록으로 확인해야 해서 "후보"라고 부른다'],
    ['순수요', '전체 수요에서 태양광·풍력이 만든 만큼을 뺀 값. 나머지 발전소(원자력·석탄·LNG 등)가 채워야 하는 양']];
  GL.forEach(([k, d], i) => {
    const y = 1.05 + i * 0.78;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y, w: 1.7, h: 0.62, rectRadius: 0.06, fill: { color: HX.teal }, line: { color: HX.teal } });
    TX(s, k, { x: 0.5, y, w: 1.7, h: 0.62, fontSize: 14, bold: true, color: 'FFFFFF', align: 'center', valign: 'middle' });
    TX(s, d, { x: 2.4, y: y + 0.05, w: 7.1, h: 0.6, fontSize: 12, valign: 'middle' });
  });
  note(s, '발표에 자주 나오는 말 다섯 가지만 먼저 설명드리겠습니다. 이용률은 발전소가 낼 수 있는 최대치 중 실제로 낸 비율입니다. 오차는 예측이 실제와 얼마나 어긋났는지이고, 낮을수록 좋습니다. 저희는 항상 "어제 값이나 지난주 값을 그대로 쓰는 방법"과 비교했습니다. 상관계수는 두 값이 함께 움직이는 정도로, 1에 가까우면 같이 움직인다는 뜻입니다. 이상 후보 알림은 평소보다 크게 떨어진 날을 표시하는 것인데, 실제 고장인지는 확인이 더 필요해서 후보라고 부릅니다. 순수요는 전체 수요에서 태양광과 풍력이 만든 만큼을 뺀 값, 즉 나머지 발전소가 채워야 하는 양입니다.');

  // ───── ① 지열·수열 ─────
  pres.addSection({ title: PART[1][1] });
  const HS = P1.heat_sources, GE = P1.geothermal, HM = P2.heat_more;
  s = slide('지열·수열은 어디에 쓰나', 1);
  img(s, 'f14_heat_sources.png', 0.5, 1.05, 5.6, 3.4);
  TX(s, bl(['지열 발전: 땅속 열로 터빈을 돌림 (국내 상업 운전 발전소 없음)', '지열 히트펌프: 땅속의 일정한 온도로 건물 냉난방', '수열: 바다·하천수의 온도 차이를 냉난방에 이용',
    `생산량은 2015년 대비 지열 ${HS.growth_2015_2024['지열']}배, 수열 ${HS.growth_2015_2024['수열']}배`]), { x: 6.4, y: 1.15, w: 3.2, h: 3.4, fontSize: 12 });
  SRC(s, '자료: 기후에너지환경부_신재생에너지 생산량(2015~2024). 원자료 단위 표기가 없어 2015년 대비 배율만 표시');
  note(s, `지열은 땅속 열을 쓰는 기술입니다. 땅속 열로 터빈을 돌리는 지열 발전은 국내에 상업 운전 중인 발전소가 없어서, 저희는 건물 냉난방에 쓰는 지열 히트펌프 자료를 찾았습니다. 수열은 바다나 하천수의 온도 차이를 냉난방에 쓰는 기술입니다. 신재생에너지 생산량 통계에서 2024년 생산량은 2015년과 비교해 지열이 ${HS.growth_2015_2024['지열']}배, 수열이 ${HS.growth_2015_2024['수열']}배가 됐습니다. 아직 규모는 작지만 빠르게 늘고 있어 운전 데이터를 모을 때입니다.`);

  s = slide('지열 히트펌프의 "평소와 다른 날"', 1);
  img(s, 'f13_geothermal.png', 0.5, 1.0, 9.0, 2.7);
  card(s, 0.5, 3.8, 2.9, 1.05, `COP ${GE.cop_median}`, 'COP: 전기 1을 써서 얻은 열 (운전 중 중앙값)');
  card(s, 3.55, 3.8, 2.9, 1.05, `${sum(GE.cop_drop_alert_days)}건`, `이상 후보 / 판정 ${num(sum(GE.judged_days))}건 (건물·날짜)`, HX.red);
  TX(s, '기준: 건물별 앞선 유효 관측일 28개의 중앙값보다 효율이 30% 넘게 낮은 날', { x: 6.6, y: 3.85, w: 2.9, h: 0.95, fontSize: 10.5, color: HX.sub });
  SRC(s, `자료: 한국수목원정원관리원_국립세종수목원 지열 이용량(${GE.period}, ${GE.buildings.length}개 건물 시간별)`);
  note(s, `국립세종수목원은 지열 히트펌프의 시간별 운전 기록을 공개하고 있습니다. 네 개 건물의 기록에서 생산한 열을 쓴 전기로 나눈 효율, 즉 COP를 매일 계산했습니다. 운전하는 동안 효율의 보통 수준(중앙값)은 ${GE.cop_median} 정도였습니다. 연료전지에 쓴 방법처럼 건물별로 평소보다 효율이 30% 넘게 낮은 날을 표시했더니, 판정한 ${num(sum(GE.judged_days))}건 가운데 ${sum(GE.cop_drop_alert_days)}건이 이상 후보로 나왔습니다. 고장인지 운전 방식 때문인지는 운전 기록과 대조해야 하지만, 지열도 데이터만 있으면 같은 AI 방법을 쓸 수 있다는 것을 보여 줍니다.`);

  s = slide('지역난방은 바깥 기온에 따라 움직인다', 1);
  card(s, 0.5, 1.15, 2.9, 1.3, f2(HM.kdhc_corr_temp_total_heat), '바깥 기온과 하루 열생산량의 상관계수 (지역난방공사, 1,002일)');
  card(s, 3.55, 1.15, 2.9, 1.3, `${HM.kdhc_external_heat_share_pct}%`, '하루 열생산 중 외부에서 받아온 열의 비중 (중앙값)', HX.amber);
  card(s, 6.6, 1.15, 2.9, 1.3, '여름·겨울', '건물 지열 사용이 몰리는 계절 (충남개발공사, 월별 2016~2025)', '7A5C99');
  TX(s, bl(['기온만 알아도 열 수요의 큰 흐름을 알 수 있다 → 열 수요 예측의 출발점', '여기서 "외부에서 받은 열"은 발전소·소각장 등에서 받아온 열로, 물을 열원으로 쓰는 재생에너지 수열과는 다르다',
    '건물 지열은 7~8월과 12~1월에 평균의 1.5~1.8배를 쓰고 4~5월·10월에는 거의 쓰지 않았다']), { x: 0.5, y: 2.75, w: 9.0, h: 2.0, fontSize: 12.5 });
  SRC(s, '자료: 한국지역난방공사_외기온도에 따른 열생산량 대비 타사 수열량, 충청남도개발공사_에너지 사용현황');
  note(s, `지역난방공사 자료에서 바깥 기온과 하루 열생산량의 상관계수가 ${f2(HM.kdhc_corr_temp_total_heat)}로 나왔습니다. 추울수록 열을 많이 만든다는 뜻이고, 기온만 알아도 열 수요의 큰 흐름을 알 수 있습니다. 하루 열생산 가운데 발전소나 소각장 같은 외부에서 받아온 열의 비중은 보통 ${HM.kdhc_external_heat_share_pct}% 정도였습니다. 이 외부 열은 물을 열원으로 쓰는 재생에너지 수열과는 다른 개념입니다. 충남개발공사 건물의 지열 사용량은 여름과 겨울에 몰리고 봄·가을 일부 달에는 거의 쓰지 않았습니다. 이것으로 첫 번째 파트를 마치겠습니다.`);

  // ───── ② 화력·원자력·바이오 ─────
  pres.addSection({ title: PART[2][1] });
  s = slide('LNG는 수요와 함께 움직인다', 2);
  img(s, 'f9_follow.png', 0.5, 1.05, 6.0, 2.6);
  s.addChart(pres.charts.BAR, [{ name: '상관계수', labels: ['LNG', '석탄', '유류'], values: [FO.corr.LNG, FO.corr['석탄'], FO.corr['유류']] }],
    { x: 6.7, y: 1.0, w: 2.8, h: 2.3, barDir: 'col', chartColors: [HX.teal, HX.muted, HX.muted], showValue: true, dataLabelPosition: 'outEnd', dataLabelFormatCode: '0.00',
      valAxisMaxVal: 1, valAxisMinVal: 0, valAxisHidden: true, catGridLine: { style: 'none' }, valGridLine: { style: 'none' }, showTitle: true, title: '하루 수요와의 상관', titleFontSize: 11, dataLabelFontSize: 11, catAxisLabelFontSize: 11 });
  TX(s, bl([`${FO.period.replace('~', ' ~ ')}, ${num(FO.days)}일`, `LNG는 수요보다 ${(FO.cv.LNG / FO.cv.demand_GWh).toFixed(1)}배 크게 오르내린다 (출렁임 정도 ${FO.cv.LNG} vs ${FO.cv.demand_GWh})`,
    `2025년 전기 도매가격(SMP)을 마지막에 정한 발전소의 연료: LNG ${P3.smp_fuel_2025['육지'].LNG}% · 유연탄 ${P3.smp_fuel_2025['육지']['유연탄']}% (육지 시간 기준)`]), { x: 0.5, y: 3.8, w: 9.0, h: 1.1, fontSize: 12 });
  SRC(s, '자료: 한국전력거래소_일별 화력발전량·시간별 발전량·SMP 결정 발전기 연료원');
  note(s, `두 번째 파트입니다. 화력은 날씨가 아니라 수요에 맞춰 출력을 조절합니다. ${num(FO.days)}일 동안 하루 전력수요와의 상관계수는 LNG ${FO.corr.LNG}, 석탄 ${FO.corr['석탄']}, 유류 ${FO.corr['유류']}로, 분석 기간에 LNG가 수요와 가장 강하게 함께 움직였습니다. LNG의 출력 변동은 수요의 약 ${(FO.cv.LNG / FO.cv.demand_GWh).toFixed(1)}배였습니다. 2025년에 전기 도매가격을 정한 발전기의 연료도 LNG가 ${P3.smp_fuel_2025['육지'].LNG}%로 가장 많았습니다. 수요 변화를 마지막에 맞추는 발전기가 가격을 정하므로 같은 해석과 맞습니다.`);

  s = slide('전날 정보로 LNG 발전량 예측', 2);
  img(s, 'f11_lng_pred.png', 0.5, 1.0, 9.0, 2.6);
  card(s, 0.5, 3.75, 2.15, 1.05, `${f1(LM[kP].nRMSE)}%`, '어제 값 그대로', HX.muted);
  card(s, 2.75, 3.75, 2.15, 1.05, `${f1(LM[kR].nRMSE)}%`, `전날까지 정보 (오차 ${pct0(LM[kR].Skill)}% 감소)`);
  card(s, 5.0, 3.75, 2.15, 1.05, `${f1(LM[kN].nRMSE)}%`, '수요 정보를 뺀 모델', HX.amber);
  card(s, 7.25, 3.75, 2.25, 1.05, `${f1(LM[kU].nRMSE)}%`, '당일 실제 수요 (사후 참고)', HX.muted);
  SRC(s, `학습 ${LP.train} · 시험 ${LP.test} ${LP.test_days}일 · 오차 = 하루 평균 LNG 발전량(${f1(LP.test_mean_GWh)} GWh) 대비 평균 오차, 간단한 통계 모델(선형회귀). 전날 집계가 예측 시각까지 나온다고 가정`);
  note(s, `LNG 발전량을 하루 단위로 예측했습니다. 2018~2020년으로 학습하고 2021년 ${LP.test_days}일로 시험했습니다. 어제 값을 그대로 쓰면 오차가 ${f1(LM[kP].nRMSE)}%인데, 전날 수요와 최근 LNG 발전량, 요일, 달을 넣은 간단한 통계 모델은 ${f1(LM[kR].nRMSE)}%로 오차를 ${pct0(LM[kR].Skill)}% 줄였습니다. 이 조건은 전날 집계가 예측 시각까지 나온다고 가정합니다. 흥미롭게도 수요 정보를 뺀 모델도 ${f1(LM[kN].nRMSE)}%로 거의 같았습니다. 그날 실제 수요를 넣으면 ${f1(LM[kU].nRMSE)}%이지만 수요는 하루가 끝나야 알 수 있어 사후 참고값입니다. 시험이 2021년 한 해뿐이라 다른 해에도 같을지는 더 확인해야 합니다.`);

  const NO = P1.nuclear_outage;
  s = slide('원전 이용률과 계획예방정비', 2);
  img(s, 'f15_nuclear_outage.png', 0.5, 1.0, 5.6, 3.6);
  card(s, 6.4, 1.05, 3.1, 1.05, f2(NO.corr_outage_days_vs_cf), '그해 정비 일수와 연간 이용률의 상관 (호기·연도 292건)', HX.red);
  TX(s, bl([`이용률 50% 미만 ${NO.low_cf_cases}건: 그해 정비 평균 ${f1(NO.low_cf_mean_outage_days)}일 (나머지 ${f1(NO.others_mean_outage_days)}일)`,
    `한빛 5호기 2020·2021·2023년 이용률 ${f1(NU.hanbit5['2020'])}·${f1(NU.hanbit5['2021'])}·${f1(NU.hanbit5['2023'])}% → 정비 ${NO.hanbit5['2020'].outage_days}·${NO.hanbit5['2021'].outage_days}·${NO.hanbit5['2023'].outage_days}일`,
    `2025.6 현황표: 운영 ${NU.operating_units}기 중 ${NU.expire_by_2030.length}기의 설계수명 만료일이 2030년 말 이내(이미 지난 호기 포함)`]), { x: 6.4, y: 2.25, w: 3.1, h: 2.6, fontSize: 11 });
  SRC(s, '자료: 한국수력원자력_원전 호기별 계획예방정비 현황·호기별 발전량 및 이용률, 원자력안전위원회_국내 원자력발전소 현황');
  note(s, `원자력은 연간 자료만 있어 예측 모델은 만들지 않았습니다. 대신 한수원의 계획예방정비 기록을 호기별 연간 이용률과 맞춰 봤습니다. 상관계수가 ${f2(NO.corr_outage_days_vs_cf)}로 나왔습니다. 정비가 길었던 해에 이용률이 낮았습니다. 이용률이 50% 미만이었던 ${NO.low_cf_cases}건은 그해 정비가 평균 ${f1(NO.low_cf_mean_outage_days)}일이었습니다. 한빛 5호기의 이용률이 낮았던 2020, 2021, 2023년도 각각 ${NO.hanbit5['2020'].outage_days}일, ${NO.hanbit5['2021'].outage_days}일, ${NO.hanbit5['2023'].outage_days}일 정비 중이었습니다. 원전에서는 출력 예측보다 정비 기록과 설비 상태를 함께 보는 것이 중요하고, 설비 상태 자료가 있으면 정비 판단을 돕는 AI를 시험할 수 있습니다.`);

  const BM = P1.biomass, BG = P3.biogas_digester;
  s = slide('바이오: 연료 품질과 생산 저하 후보', 2);
  img(s, 'f18_biomass.png', 0.5, 1.0, 4.4, 2.6);
  img(s, 'f26_biogas_digester.png', 5.05, 1.0, 4.45, 2.6);
  TX(s, bl([`바이오 연료 ${BM.samples}건: 수분이 많을수록 발열량이 낮다 (순위 상관 ${BM.spearman_moisture_heating_value}) → 원료 품질을 미리 알면 연소 조건을 맞출 수 있다`,
    `하수처리장 소화조: 바이오가스 생산이 평소(28일 중앙값)보다 40% 이상 줄어든 날 ${BG.alert_days}일 / ${num(BG.days)}일 → 이상 후보 알림`]), { x: 0.5, y: 3.75, w: 9.0, h: 1.1, fontSize: 12 });
  SRC(s, '자료: 한국동서발전_바이오매스 연료분석결과(2017~2018), 광주환경공단_혐기성 소화조 운영 데이터(2020~2025)');
  note(s, `바이오는 두 자료를 봤습니다. 동서발전의 바이오 연료 분석 ${BM.samples}건에서는 수분이 많을수록 발열량이 낮았습니다. 원료 품질을 미리 알면 연소 조건을 맞출 수 있다는 근거입니다. 광주 하수처리장의 소화조에서는 바이오가스 생산이 평소보다 40% 이상 줄어든 날이 ${BG.alert_days}일 있었습니다. 연료전지와 같은 이상 후보 알림입니다. 두 결과는 서로 다른 자료에서 본 것입니다. 이것으로 두 번째 파트를 마칩니다.`);

  // ───── ③ 태양광·풍력·수력 ─────
  pres.addSection({ title: PART[3][1] });
  s = slide('태양광 하루 전 예측', 3);
  img(s, 'f1_models.png', 0.5, 1.0, 5.4, 3.1);
  card(s, 6.2, 1.05, 3.3, 1.05, `${f1(M.share)}%`, `전국 태양광 ${f1(M.total / 1000)}GW 중 계량 집계분 (2024.12.1 자료)`, HX.amber);
  TX(s, bl([`17개 시도 시간별 이용률(발전량 ÷ 설비용량)`, `학습 2020~22 · 검증 2023 · 시험 2024, 낮 시간`, `AI 모델(LightGBM) ${f2(A.LightGBM.nRMSE)}% (3회 평균): 어제 값 ${f2(A.Persistence.nRMSE)}% 대비 오차 ${pct0(A.LightGBM.Skill)}% 감소`,
    '입력 기상은 그 시각의 관측값']), { x: 6.2, y: 2.25, w: 3.3, h: 2.6, fontSize: 11.5 });
  SRC(s, '자료: 한국동서발전_전국 태양광 발전량 예측값 학습데이터·예측값. 오차 = 설비용량 대비 평균 오차(%)');
  note(s, `세 번째 파트입니다. 2024년 12월 1일 발표 자료에서 전국 태양광 설비 ${f1(M.total / 1000)}GW 가운데 계량 집계분은 ${f1(M.share)}%였습니다. 저희는 이 계량 설비의 17개 시도 시간별 이용률로 하루 전 예측 모델을 만들었습니다. 2020~2022년으로 학습하고 2023년으로 검증, 2024년 낮 시간으로 시험했습니다. 어제 같은 시각 값을 그대로 쓰면 설비용량 대비 오차가 ${f2(A.Persistence.nRMSE)}%, AI 모델(LightGBM)은 세 번 학습한 평균 ${f2(A.LightGBM.nRMSE)}%로 오차를 약 ${pct0(A.LightGBM.Skill)}% 줄였습니다. 중요한 조건이 있습니다. 여기 넣은 기상은 예보가 아니라 그 시각의 관측값입니다.`);

  s = slide('관측 기상 조건과 "전날 14시" 조건', 3);
  img(s, 'f2_weather_info.png', 0.5, 1.0, 4.6, 3.0);
  const T3 = [[{ text: '조건 (2024 낮, 같은 평가 행)', options: { bold: true } }, { text: '오차', options: { bold: true } }],
    ['이틀 전 같은 시각 값', `${f2(SI.lag48_baseline.nRMSE)}%`], ['전날 14시 가정 · 기상 미사용', `${f2(SI.lightgbm.nRMSE)}%`], ['관측 기상 사용 (참고)', `${f2(SI.observed_weather_reference.nRMSE)}%`],
    ['실제 기상 예보 사용', '측정 안 함']];
  s.addTable(T3, { x: 5.35, y: 1.05, w: 4.15, colW: [2.9, 1.25], fontSize: 11.5, border: { type: 'solid', color: HX.grid, pt: 0.75 }, fill: { color: 'FFFFFF' }, margin: 0.06 });
  TX(s, `전날 14시 가정 모델은 관측 기상과 24시간 전 값을 모두 빼고 48시간 전 값을 썼다. 두 값의 차이를 모두 날씨 효과로 볼 수는 없다. 같은 조건의 80% 범위 포함률 ${SII.calibrated.coverage_pct}% (월별 ${Math.min(...Object.values(SII.by_month).map(v => v.coverage_pct)).toFixed(0)}~${Math.max(...Object.values(SII.by_month).map(v => v.coverage_pct)).toFixed(0)}%)`,
    { x: 5.35, y: 3.25, w: 4.15, h: 1.6, fontSize: 10.5, color: HX.sub });
  SRC(s, '왼쪽 그림: 기상 정보 수준별 오차(관측 기상 실험, 단일 실행 6.04%). 오른쪽 표: solar_issue_14');
  note(s, `그래서 실제로 하루 전에 알 수 있는 정보만으로도 예측해 봤습니다. 전날 오후 2시에 예측한다고 가정하고 관측 기상과 24시간 전 값을 빼고, 48시간 전 값과 날짜·시각 정보만 썼습니다. 같은 시간대에서 이틀 전 값을 그대로 쓰면 ${f2(SI.lag48_baseline.nRMSE)}%, 이 모델은 ${f2(SI.lightgbm.nRMSE)}%, 관측 기상을 넣은 모델은 ${f2(SI.observed_weather_reference.nRMSE)}%였습니다. 입력 조건이 여러 개 함께 달라서 차이를 모두 날씨 효과로 볼 수는 없고, 실제 기상 예보를 넣은 성능은 아직 측정하지 않았습니다. 이것이 다음 과제입니다.`);

  const KS = P2.khnp_solar;
  s = slide('발전소 54곳에서도 같은 순서', 3);
  img(s, 'f21_khnp_solar.png', 0.5, 1.0, 5.6, 3.6);
  TX(s, bl([`한수원 태양광 ${KS.plants}곳, 2023~24 학습 · 2025 시험, 낮 시간`, `어제 값 ${f1(KS.nRMSE.persistence)}% → 기상 없음 ${f1(KS.nRMSE['기상 없음'])}% → 예보에도 있는 항목 ${f1(KS.nRMSE['예보 항목(기온·습도·풍속·강수)'])}% → 실측 일사까지 ${f1(KS.nRMSE['+ 실측 일조·일사'])}%`,
    '기상은 발전소 인근 관측값 (실제 예보 아님)', '시도 실험과 연도·자료가 달라 오차 크기는 직접 비교하지 않는다']), { x: 6.4, y: 1.1, w: 3.1, h: 3.7, fontSize: 11.5 });
  SRC(s, '자료: 한국수력원자력_기상정보를 융합한 한수원 태양광 시계열 발전정보');
  note(s, `시도 합계는 발전소마다의 오차가 서로 상쇄될 수 있어서, 발전소 단위로도 확인했습니다. 한수원 태양광 ${KS.plants}곳의 시간별 발전량과 인근 기상 자료로 2025년을 시험하니 어제 값 ${f1(KS.nRMSE.persistence)}%, 기상 없이 ${f1(KS.nRMSE['기상 없음'])}%, 예보에도 있는 항목을 넣으면 ${f1(KS.nRMSE['예보 항목(기온·습도·풍속·강수)'])}%, 실측 일사까지 넣으면 ${f1(KS.nRMSE['+ 실측 일조·일사'])}%였습니다. 기상 정보를 더할수록 오차가 줄어드는 순서가 발전소 단위에서도 같았습니다.`);

  const WS = P2.wind_scada, JH = WS['장흥풍력'], HSW = WS['화순풍력'];
  const top3 = Object.entries(HSW.stopped_by_unit).sort((a, b) => b[1] - a[1]).slice(0, 3);
  s = slide('풍력은 풍속과 함께 봐야 한다', 3);
  img(s, 'f19_wind_scada.png', 0.5, 1.0, 9.0, 3.0);
  TX(s, bl([`장흥풍력: 과거 출력 기준 ${f1(JH.nRMSE_persistence_24h)}% → 실제 풍속 + 출력 곡선 ${f1(JH.nRMSE_curve_with_actual_wind)}% (2025년)`,
    `화순풍력: 바람이 충분한데(5~12 m/s) 이용률 1% 이하인 시간이 ${top3.map(([k, v]) => `${k}호기 ${num(v)}`).join(', ')}시간에 집중 → "평소와 다른 호기" 후보`]), { x: 0.5, y: 4.05, w: 9.0, h: 0.85, fontSize: 11.5 });
  SRC(s, '자료: 한국서부발전_장흥·화순풍력발전소 스카다 발전 정보. 정지 원인(고장·출력제어)은 기록과 대조 필요');
  note(s, `풍력은 발전량만 봐서는 평소와 다른 날을 가려내기 어려웠습니다. 그래서 풍속과 출력이 함께 기록된 서부발전 풍력발전소 운전 기록을 찾았습니다. 운전 중인 시간으로 풍속별 출력 곡선을 만들면, 장흥풍력은 과거 출력 기준 ${f1(JH.nRMSE_persistence_24h)}%에서 실제 풍속을 넣은 출력 곡선 ${f1(JH.nRMSE_curve_with_actual_wind)}%로 오차가 줄었습니다. 풍속 예보가 정확할수록 이 값에 가까워질 것입니다. 화순풍력에서는 바람이 충분한데도 이용률이 1% 이하였던 시간이 ${top3.map(([k]) => k + '호기').join(', ')}에 몰려 있었습니다. 같은 단지의 호기끼리 비교하면 평소와 다른 호기가 보입니다. 멈춘 이유가 고장인지 출력제어인지는 기록과 대조해야 합니다.`);

  const SS = P3.seongsan_wind.low_days_by_unit;
  s = slide('소수력·풍력의 이상 후보 알림', 3);
  img(s, 'f12_wind_hydro.png', 0.5, 1.0, 4.6, 2.7);
  img(s, 'f25_seongsan_peer.png', 5.2, 1.0, 4.3, 2.7);
  TX(s, bl([`중부발전 설비에 두 규칙(설비용량 15%p 넘게 하락 / 평소의 절반 넘게 하락) 적용: 제주상명풍력 ${WH['제주상명풍력'].days}일 동안 0건, 양양풍력은 기록 1일로 판정 불가`,
    `소수력: 15%p 규칙에서 보령화력소수력#2가 ${WH['보령화력소수력#2'].alerts}일(${WH['보령화력소수력#2'].events}구간) — 강수·유량과 대조 전에는 갈수기와 구분 불가`,
    `성산풍력 10기 풍속 비교: 1·5호기만 단지 평균보다 20% 이상 약한 날이 많음(${SS['성산1호기']}·${SS['성산5호기']}일)`]), { x: 0.5, y: 3.8, w: 9.0, h: 1.1, fontSize: 10.5 });
  SRC(s, '자료: 한국중부발전_신재생에너지 발전량, 한국남부발전_성산풍력 일평균 풍속데이터');
  note(s, `연료전지에 쓴 규칙을 풍력과 소수력에도 적용했습니다. 제주상명풍력은 ${WH['제주상명풍력'].days}일 동안 두 규칙 모두 알림이 0건이었습니다. 바람 때문에 매일 크게 출렁이니 발전량만으로는 튀는 날이 드러나지 않는다는 뜻입니다. 소수력은 보령화력소수력 2호기가 ${WH['보령화력소수력#2'].alerts}일로 가장 많았지만, 강수와 유량을 보기 전에는 가뭄 때문인지 설비 문제인지 구분할 수 없습니다. 반면 성산풍력 10기의 풍속을 같은 날끼리 비교하면 1호기와 5호기만 자주 약했습니다. 풍력은 같은 단지 안에서 비교하는 방법이 맞습니다. 이것으로 세 번째 파트를 마칩니다.`);

  // ───── ④ 종합 및 모델 생성 ─────
  pres.addSection({ title: PART[4][1] });
  const RS = P1.renewables_2025.by_source;
  s = slide('발전원마다 다른 질문', 4);
  img(s, 'f16_source_variability.png', 0.5, 1.0, 5.0, 3.1);
  const T4 = [[{ text: '출력을 정하는 것', options: { bold: true } }, { text: '발전원', options: { bold: true } }, { text: 'AI의 역할', options: { bold: true } }],
    ['날씨', '태양광·풍력·소수력', '하루 전 예측'], ['수요', 'LNG', '추종 분석·일별 예측'], ['설비', '연료전지·지열·바이오', '이상 후보 알림'], ['정비', '원자력', '정비 기록과 상태 감시'], ['사용량', '전체', '수요 예측 → 발전 계획']];
  s.addTable(T4, { x: 5.7, y: 1.05, w: 3.8, colW: [1.0, 1.45, 1.35], fontSize: 10.5, border: { type: 'solid', color: HX.grid, pt: 0.75 }, margin: 0.05 });
  TX(s, `2025년 실적에서 어제 값 예측 오차: 연료전지 ${f1(RS['연료전지'].dayahead_persistence_nRMSE)}% · 풍력 ${f1(RS['풍력'].dayahead_persistence_nRMSE)}% — 기준선 오차가 큰 발전원일수록 예측의 여지가 크다`, { x: 5.7, y: 3.5, w: 3.8, h: 1.3, fontSize: 10.5, color: HX.sub });
  SRC(s, '자료: 한국전력거래소_신재생 발전량 및 설비용량(2025 시간별). 태양광은 밤 시간 포함');
  note(s, `마지막 파트입니다. 지금까지 본 것을 한 표로 정리하면, 출력을 날씨가 정하는 발전원은 하루 전 예측, 수요가 정하는 LNG는 추종 분석과 일별 예측, 설비가 정하는 연료전지·지열·바이오는 이상 후보 알림, 원자력은 정비 기록과 상태 감시가 AI의 역할입니다. 2025년 실적에서 어제 값으로 예측했을 때 오차가 연료전지는 ${f1(RS['연료전지'].dayahead_persistence_nRMSE)}%, 풍력은 ${f1(RS['풍력'].dayahead_persistence_nRMSE)}%였습니다. 기준선 오차가 큰 발전원일수록 예측의 여지가 크다는 단서입니다.`);

  const PN = PL.net, PD = PL.demand;
  s = slide('우리의 목표: 수요에 맞춘 발전 계획', 4);
  img(s, 'f27_plan_day.png', 0.5, 1.0, 9.0, 3.05);
  TX(s, bl(['① 내일 전력수요 예측 → ② 내일 태양광·풍력 예측 → ③ 나머지 발전소가 채울 양(순수요) 계산',
    `④ 하루 종일 일정한 원자력(약 ${num(PL.plan.nuclear_MW)} MW, 가정)을 먼저 놓고 나머지를 석탄·LNG 등 조절 가능한 발전으로 채우는 계획 (전날 오후 2시 작성)`]), { x: 0.5, y: 4.1, w: 9.0, h: 0.8, fontSize: 11.5 });
  SRC(s, `자료: 한국전력거래소_시간별 전국 전력수요량·신재생 발전량 및 설비용량(2025). 예시: ${PL.example_day} (쉬는 날 다음 평일)`);
  note(s, `이제 저희 목표인 발전 계획 AI입니다. 순서는 네 단계입니다. 먼저 내일 사람들이 전기를 얼마나 쓸지 예측하고, 내일 태양광과 풍력이 얼마나 만들지 예측합니다. 수요에서 태양광·풍력을 빼면 나머지 발전소가 채워야 하는 양이 나옵니다. 하루 종일 일정하게 돌아가는 원자력을 먼저 놓고, 나머지를 석탄이나 LNG처럼 출력을 조절할 수 있는 발전소로 채우는 계획을 전날 오후 2시에 세웁니다. 그림은 ${PL.example_day.replace(/-/g, '.')}의 계획과 실제입니다.`);

  s = slide('AI 계획으로 줄인 대기 발전량', 4);
  img(s, 'f28_plan_reserve.png', 0.5, 1.0, 5.8, 3.4);
  card(s, 6.5, 1.05, 3.0, 1.1, `${num(PL.reserve_saving_MW)} MW`, `예측이 틀릴 때를 대비해 대기할 발전량 감소 (${num(PN['지난주 같은 시각'].reserve_P95_MW)} → ${num(PN.AI.reserve_P95_MW)})`);
  TX(s, bl([`수요 예측 오차: 지난주 값 ${f1(PD['지난주 같은 시각'].MAPE_pct)}% → AI ${f1(PD.AI.MAPE_pct)}%`, `실제보다 많이 준비한 전력량 ${num(Math.round(PL.over_saving_GWh))} GWh 감소 (2025년 9~12월)`,
    '태양광·풍력은 날씨 예보가 없어 아직 지난주 값과 비슷 → 날씨 자료를 넣는 것이 다음 단계']), { x: 6.5, y: 2.3, w: 3.0, h: 2.5, fontSize: 11 });
  SRC(s, '2025년 1~8월로 시작해 매달 다시 학습, 9~12월 시험. 대기 발전량 = 예측이 틀린 크기의 95% 지점. 실제 급전(발전기별 비용·제약)은 반영하지 않은 시제품');
  note(s, `이 계획이 얼마나 효율적인지 2025년 9월부터 12월까지 시험했습니다. 비교 대상은 지난주 같은 시각의 값을 그대로 쓰는 방법입니다. 수요 예측 오차가 ${f1(PD['지난주 같은 시각'].MAPE_pct)}%에서 ${f1(PD.AI.MAPE_pct)}%로 줄었습니다. 예측이 틀릴 때를 대비해 늘 대기시켜 둬야 하는 발전량은 ${num(PN['지난주 같은 시각'].reserve_P95_MW)} MW에서 ${num(PN.AI.reserve_P95_MW)} MW로 약 ${num(PL.reserve_saving_MW)} MW 줄었습니다. 대기하는 발전소가 줄면 그만큼 연료를 덜 쓰고 효율적으로 생산할 수 있습니다. 다만 태양광과 풍력은 아직 날씨 예보를 넣지 못해 지난주 값과 비슷했고, 날씨 자료를 넣는 것이 다음 단계입니다. 실제 발전소별 비용과 제약을 반영하지 않은 시제품이라는 점도 함께 말씀드립니다.`);

  const PW = PL.with_weather;
  const reserveWithoutWeather = PN.AI.reserve_P95_MW;
  const reserveWithWeather = PW.net.AI.reserve_P95_MW;
  s = slide('날씨를 넣으면 더 줄어든다', 4);
  img(s, 'f29_plan_weather.png', 0.5, 1.0, 9.0, 3.0);
  TX(s, bl([
    `날씨를 넣었을 때 대기 발전량은 ${num(reserveWithoutWeather)} → ${num(reserveWithWeather)} MW`,
    `발전량 오차는 태양광 ${PL.solar.AI_nMAE_pct}% → ${PW.solar.AI_nMAE_pct}%, 풍력 ${PL.wind.AI_nMAE_pct}% → ${PW.wind.AI_nMAE_pct}% (설비용량 대비)`,
    '그 시각에 실제로 관측한 날씨라 실제 예보보다 좋은 참고값입니다.',
  ]), { x: 0.5, y: 4.06, w: 9.0, h: 0.93, fontSize: 11.5 });
  SRC(s, '자료 기상청 ASOS·한국전력거래소. 2025년 9~12월 같은 시간으로 비교');
  note(s, `앞 슬라이드와 같은 시간에 날씨를 더해 비교했습니다. 태양광에는 햇빛의 양과 비친 시간, 구름의 양, 기온을 넣었습니다. 풍력에는 바람의 세기를 넣고, 냉방과 난방에 쓰이는 전기를 예측할 때는 기온과 습도를 넣었습니다. 왼쪽 막대는 예측이 빗나갈 때를 대비해 대기시킬 발전량입니다. 시험 시간의 95%에서 오차를 감당할 수 있는 크기로, 날씨 없이 계산하면 ${num(reserveWithoutWeather)} MW, 관측 날씨를 넣으면 ${num(reserveWithWeather)} MW였습니다. 오른쪽은 태양광과 풍력의 예측 오차를 각각의 설비용량으로 나눈 값입니다. 막대가 낮을수록 예측이 실제에 더 가까웠다는 뜻입니다. 이 실험은 전날 미리 알 수 없는 실제 관측 날씨를 썼습니다. 실제 예보보다 좋은 참고값으로 봐 주세요.`);

  const PF = PL.forecast_sample;
  const { no_weather: FN, observed: FOB, forecast: FF } = PF.conditions;
  const pct2 = (v) => v.toFixed(2);
  s = slide('실제 예보를 넣으면?', 4);
  img(s, 'f30_plan_forecast.png', 0.5, 1.02, 6.4, 2.55);
  card(s, 7.0, 1.36, 2.5, 1.45, `${num(FF.net_reserve_P95_MW)} MW`, '실제 예보로 계산한 대기 발전량');
  TX(s, bl([
    '전날 오후 2시 기상청 예보로 다음 날 발전량을 맞혀 봤어요.',
    `관측 날씨 → 실제 예보로 바꾸니 풍력 오차는 ${pct2(FOB.wind_nMAE_pct)}% → ${pct2(FF.wind_nMAE_pct)}%.`,
    `전기 사용량 오차는 ${pct2(FOB.demand_MAPE_pct)}% → ${pct2(FF.demand_MAPE_pct)}%. 낮 시간 2주만 비교했어요.`,
  ]), { x: 0.5, y: 3.62, w: 9.0, h: 1.13, fontSize: 12 });
  SRC(s, `자료 기상청 단기예보·ASOS, 전력거래소. 2025년 11월 17~30일 07~18시, ${PF.test_hours}시간`);
  note(s, `이번에는 전날 오후 두 시에 받은 기상청 예보로 다음 날을 맞혀 봤습니다. 예보에서 구할 수 있는 기온, 습도, 바람 세기, 구름 정보로 모델을 학습했습니다. 같은 모델에 관측 날씨와 실제 예보를 번갈아 넣고, 날씨 없이 내놓은 예측과도 비교했습니다. 막대가 낮을수록 실제 발전량에 가깝습니다. 풍력 오차는 관측 날씨에서 ${pct2(FOB.wind_nMAE_pct)}%, 예보에서 ${pct2(FF.wind_nMAE_pct)}%였습니다. 예측이 빗나갈 때를 대비해 대기할 발전량은 날씨 없이 ${num(FN.net_reserve_P95_MW)} MW, 관측 날씨로 ${num(FOB.net_reserve_P95_MW)} MW, 예보로 ${num(FF.net_reserve_P95_MW)} MW였습니다. 11월 낮 시간만 본 2주 표본이라 참고값으로 봐 주세요.`);

  s = slide('모델보다 먼저 한 일: 데이터 점검', 4);
  img(s, 'f4_normalize.png', 0.5, 1.0, 9.0, 2.6);
  TX(s, bl(['태양광 시도·시각 중복 66,976행 제거 (806,408 → 739,432행)', '관측 일사량이 계산값보다 큰 27,566건: 시각·단위 점검 후보로 표시',
    '중부발전 2025년 1~6월 발전량 1,000배 기록 5,370행 보정', `발전량 대신 이용률로 학습 → 평균 치우침 ${f1(D['원시 발전량(MWh) 학습'].bias)}%p → +${f1(D['이용률(CF) 학습'].bias)}%p`]), { x: 0.5, y: 3.7, w: 9.0, h: 1.2, fontSize: 11.5 });
  note(s, `모델을 만들기 전에 데이터부터 점검했습니다. 태양광 자료에서 시도와 시각이 겹치는 중복 66,976행을 지웠고, 관측 일사량이 계산한 대기권 밖 일사량보다 큰 27,566건은 시각이나 단위를 점검할 후보로 표시했습니다. 중부발전 자료는 2025년 1~6월 발전량이 1,000배로 기록돼 있어 5,370행을 고쳤습니다. 또 설비가 해마다 늘어나기 때문에 발전량 대신 설비용량 대비 이용률로 학습했고, 그 결과 예측의 평균 치우침이 ${f1(D['원시 발전량(MWh) 학습'].bias)}%포인트에서 0.43%포인트로 줄었습니다.`);

  s = slide('코드로 만든 과정 6단계', 4);
  const shots = [['s1_audit.png', '① 점검'], ['s2_preprocess.png', '② 전처리'], ['s3_train.png', '③ 학습'], ['s4_eval.png', '④ 평가'], ['s5_anomaly.png', '⑤ 이상 후보'], ['s6_run.png', '⑥ 실행']];
  shots.forEach(([f, cap], i) => {
    const x = 0.5 + (i % 3) * 3.05, y = 1.0 + Math.floor(i / 3) * 1.98;
    s.addImage({ path: path.join(E, 'figures/code', f), x, y, w: 2.85, h: 1.65, altText: cap });
    TX(s, cap, { x, y: y + 1.66, w: 2.85, h: 0.26, fontSize: 10, bold: true, align: 'center' });
  });
  SRC(s, '코드: energy/audit.py, analyze.py, analyze_extra.py, analyze_public*.py · 원 데이터 받기: fetch_data.py');
  note(s, '코드는 여섯 단계로 이뤄져 있습니다. 첫째, 데이터 점검 코드가 중복, 시각 어긋남, 단위 오류를 찾습니다. 둘째, 발전량을 이용률로 바꾸고, 23시 다음이 0시인 것처럼 시각과 날짜가 이어지도록 숫자를 바꿉니다. 셋째, 과거 값과 날씨 항목으로 AI 모델(LightGBM)을 학습합니다. 넷째, 어제 값 기준과 비교해 평가합니다. 다섯째, 평소 패턴에서 크게 벗어난 날을 이상 후보로 표시합니다. 여섯째, 공공데이터포털에서 원 데이터를 다시 받아 실행하면 같은 결과가 다시 만들어집니다.');

  s = slide('점 하나가 아니라 범위로', 4);
  img(s, 'f3_days.png', 0.5, 1.0, 9.0, 3.1);
  TX(s, `아래쪽·위쪽 예측을 따로 만들어 "80% 범위"를 구하고 2023년 자료로 폭을 조정 → 2024년 실제값의 ${(IV.calibrated_coverage * 100).toFixed(1)}%가 범위 안 (조정 전 ${(IV.raw_coverage * 100).toFixed(1)}%). 맑은 날은 범위가 좁고, 크게 틀린 날에는 오후 발전량을 낮게 예측했다.`,
    { x: 0.5, y: 4.15, w: 9.0, h: 0.7, fontSize: 11.5 });
  SRC(s, `전남 ${R.fig_days.good}(맑은 날)과 ${R.fig_days.worst}(크게 틀린 날), 관측 기상 모델`);
  note(s, `AI는 숫자 하나 대신 "이 사이에 들어올 것"이라는 범위도 알려 줍니다. 80% 범위를 목표로 했는데 처음에는 실제값의 ${(IV.raw_coverage * 100).toFixed(1)}%만 들어왔고, 2023년 자료로 폭을 조정하자 2024년에 ${(IV.calibrated_coverage * 100).toFixed(1)}%가 들어왔습니다. 맑은 날에는 범위가 좁고 잘 맞았지만, 크게 틀린 날에는 오후 발전량을 낮게 예측했습니다. 불확실성은 줄일 수 있지만 없앨 수는 없다는 것을 보여 줍니다.`);

  const FC = R.fuelcell, fcA = sum(Object.fromEntries(Object.entries(FC).map(([k, v]) => [k, v.alerts]))), fcE = sum(Object.fromEntries(Object.entries(FC).map(([k, v]) => [k, v.events])));
  s = slide('이상 후보 알림은 어떻게 읽나', 4);
  img(s, 'f8_fuelcell.png', 0.5, 1.1, 5.4, 3.6);
  TX(s, bl([`연료전지 5기: 최근 28일 보통 수준보다 평소 흔들림의 3배 넘게, 그리고 설비용량의 15%p 넘게 떨어진 날 ${fcA}일, 연속 알림을 묶어 ${fcE}구간`,
    `28일 기준은 천천히 떨어지는 저하를 따라가 놓친다 → 처음 90일을 기준으로 작은 하락을 계속 더해 보는 방법(누적합)에서 세종연료전지 첫 후보일 ${CU['세종연료전지'].first_alert_date}`,
    `남부발전 연료전지도 ${P2.kospo_fuelcell.declining_over_1pp_per_year.length}개 계열이 해마다 1%p 넘게 하락`, '"고장"이 아니라 "후보": 정비 기록과 대조해야 확인된다']), { x: 6.1, y: 1.05, w: 3.4, h: 3.8, fontSize: 10.5 });
  SRC(s, '자료: 한국중부발전_신재생에너지 발전량, 한국남부발전_연료전지 발전실적');
  note(s, `연료전지는 출력이 거의 일정해서 예측보다 평소와 다른 날을 찾는 것이 의미 있습니다. 최근 28일의 보통 수준보다 크게, 그리고 설비용량의 15%포인트 넘게 떨어진 날을 표시했더니 5기에서 ${fcA}일, 연속된 날을 묶으면 ${fcE}구간이 나왔습니다. 하지만 28일 기준은 천천히 떨어지는 저하를 따라가 버립니다. 처음 90일을 기준으로 두고 작은 하락을 계속 더해 보는 방법에서는 세종연료전지가 ${CU['세종연료전지'].first_alert_date.replace(/-/g, '.')}부터 지속 저하 후보로 잡혔습니다. 다만 기준 기간이 겨울이라 결과가 기준 설정에 민감합니다. 이 결과들은 고장이 아니라 후보이고, 정비 기록과 대조해야 확인됩니다.`);

  s = slide('확인한 것과 다음 검증', 4);
  const T5 = [[{ text: '확인한 것', options: { bold: true } }, { text: '조건', options: { bold: true } }, { text: '다음 검증', options: { bold: true } }],
    [`수요 계획 AI: 대기 발전량 ${num(PL.reserve_saving_MW)} MW 감소`, '2025년 9~12월, 날씨 미사용', '날씨 예보·발전기별 비용 반영'],
    [`태양광 오차 ${pct0(A.LightGBM.Skill)}% 감소, 발전소 54곳 같은 순서`, '관측 기상 입력', '과거 기상 예보로 같은 평가'],
    [`LNG 일별 오차 ${pct0(LM[kR].Skill)}% 감소`, '2021년 한 해 시험', '다른 해·예측 수요로 재시험'],
    ['연료전지·지열·바이오·풍력 호기 이상 후보', '정비 기록 미대조', '정비·정지 기록과 대조'],
    [`원전 정비 일수–이용률 상관 ${f2(NO.corr_outage_days_vs_cf)}`, '연 단위 자료', '설비 상태 자료 확보'],
    ['물리 한계(카르노·베츠·쇼클리–퀘이서)는 AI로 넘지 못함', '—', '—']];
  s.addTable(T5, { x: 0.5, y: 1.0, w: 9.0, colW: [4.0, 2.2, 2.8], fontSize: 10.5, border: { type: 'solid', color: HX.grid, pt: 0.75 }, margin: 0.06 });
  note(s, `정리하겠습니다. 수요에 맞춘 발전 계획 AI는 대기해야 하는 발전량을 약 ${num(PL.reserve_saving_MW)} MW 줄였고, 다음은 날씨 예보와 발전기별 비용을 넣는 것입니다. 태양광은 관측 기상 조건에서 오차를 ${pct0(A.LightGBM.Skill)}% 줄였고 발전소 54곳에서도 같은 순서를 확인했지만, 실제 기상 예보로 다시 재는 것이 다음 과제입니다. LNG는 전날 정보로 오차를 ${pct0(LM[kR].Skill)}% 줄였지만 2021년 한 해만 시험했습니다. 연료전지, 지열, 바이오, 풍력 호기의 이상 후보는 정비 기록과 대조해야 실제 고장인지 알 수 있습니다. 원전은 정비와 이용률의 관계를 확인했고, 설비 상태 자료가 있으면 한 걸음 더 갈 수 있습니다. 그리고 AI는 카르노·베츠·쇼클리–퀘이서 같은 물리 한계를 넘지 못합니다.`);

  s = slide('수요를 알고, 예측하고, 낭비 없이 만든다', 0, 'DARK');
  TX(s, '설비를 더 짓기 전에, 이미 있는 설비를 더 잘 알자 · 감사합니다', { x: 0.6, y: 3.05, w: 8.8, h: 0.5, fontSize: 18, color: 'CFE3E1' });
  TX(s, '데이터: 공공데이터포털(data.go.kr) 파일데이터 50종 — 한국동서발전·한국중부발전·한국남부발전·한국서부발전·한국남동발전·한국수력원자력·한국전력거래소·원자력안전위원회 등 (목록: energy/report/데이터목록.md)   ·   코드: energy/analyze*.py',
    { x: 0.6, y: 4.3, w: 8.8, h: 0.8, fontSize: 10, color: 'A9C9C6' });
  note(s, '사람들이 얼마나 쓸지 알고, 발전소마다 얼마나 만들지 예측해서, 낭비 없이 생산한다. 설비를 더 짓기 전에 이미 있는 설비를 더 잘 아는 것이 저희의 결론입니다. 감사합니다.');

  // ───── 보충 슬라이드 (질문용) ─────
  pres.addSection({ title: '보충' });
  s = slide('보충: 공식 예측과 하루 비교', 4);
  img(s, 'f7_kpx_day.png', 0.5, 1.0, 5.4, 3.6);
  TX(s, bl([`2024-12-02 낮 ${KD.n}개 시도·시각`, `공식 하루 전 예측 ${f2(KD['공식 하루 전 예측'].nRMSE)}% · 어제 값 ${f2(KD.Persistence.nRMSE)}% · 관측 기상 모델 ${f2(KD['우리 모델(관측 기상 입력)'].nRMSE)}%`,
    '입력(예보 vs 관측)과 시스템이 함께 다르고 하루치라 우열을 판단할 수 없다']), { x: 6.1, y: 1.1, w: 3.4, h: 3.6, fontSize: 11.5 });
  note(s, '질문이 나오면 쓰는 보충 슬라이드입니다. 2024년 12월 2일 하루를 공식 예측과 비교했지만, 입력과 시스템이 함께 다르고 하루치라 우열을 판단할 수 없습니다.');

  s = slide('보충: 출력제어와 돈 환산(참고)', 4);
  img(s, 'f17_curtailment.png', 0.5, 1.0, 5.4, 3.5);
  const VAL = P1.forecast_value;
  TX(s, bl([`육지 태양광 출력제어 2024 ${P1.curtailment.days_by_year['육지 태양광 출력제어횟수']['2024']}일 → 2025 ${P1.curtailment.days_by_year['육지 태양광 출력제어횟수']['2025']}일`,
    `태양광 nMAE 차이 ${VAL.nMAE_reduction_pp}%p × 2024 낮 설비용량 ≈ ${num(VAL.abs_error_reduction_GWh)} GWh × SMP 단순평균 ${VAL.smp_2024_won_per_kWh}원/kWh ≈ ${num(Math.round(VAL.value_100M_won))}억 원`,
    '단순 환산값 — 실제 절감액으로 해석할 수 없음']), { x: 6.1, y: 1.1, w: 3.4, h: 3.6, fontSize: 11 });
  note(s, '보충 슬라이드입니다. 출력제어가 늘고 있다는 현황과, 예측 개선을 전기 도매가격으로 단순 환산한 참고값입니다. 실제 절감액이 아니라는 점을 함께 말합니다.');

  const CAT = JSON.parse(fs.readFileSync(path.join(E, 'report/catalog.json'), 'utf8'));
  s = slide('보충: 사용한 공공데이터 50종', 4);
  const byG = ['기본', '1차', '2차', '3차'].map(g => [g, CAT.filter(c => c.group === g).length]);
  const byP = ['①', '②', '③', '④'].map(p => [p, CAT.filter(c => c.part.includes(p)).length]);
  card(s, 0.5, 1.1, 2.2, 1.2, '50종', `제공 기관 ${new Set(CAT.map(c => c.org)).size}곳`);
  TX(s, bl(byG.map(([g, n]) => `${g} ${n}종` + ({ 기본: ' — 처음 받은 자료', '1차': ' — 직접 검색', '2차': ' — GPT 웹 조사', '3차': ' — GPT 웹 조사' }[g]))), { x: 3.0, y: 1.15, w: 3.2, h: 1.6, fontSize: 12 });
  TX(s, bl(byP.map(([p, n]) => `${p} ${PART['①②③④'.indexOf(p) + 1][1]} ${n}종`)), { x: 6.4, y: 1.15, w: 3.1, h: 1.6, fontSize: 12 });
  TX(s, '전체 목록(포털 번호·기관·쓴 곳·핵심 결과): energy/report/데이터목록.md, 보고서 부록 B. 한 자료가 여러 파트에 걸치면 중복 집계', { x: 0.5, y: 3.0, w: 9.0, h: 0.6, fontSize: 11, color: HX.sub });
  note(s, '보충 슬라이드입니다. 분석에 쓴 공공데이터 50종의 구성입니다. 전체 목록은 보고서 부록 B와 데이터 목록 문서에 있습니다.');

  const out = path.join(E, 'report/발표자료_최종.pptx');
  await pres.writeFile({ fileName: out });
  await applyTheme(out, THEME);
  const md = ['# 발표 대본 — 발전원별 AI 예측·관리 시스템', '',
    '> `report/발표자료_최종.pptx`의 발표자 노트에서 자동으로 만든 대본이다(`node build/deck_final.js`). 수치는 `results/results.json` 값이다. 슬라이드를 고치면 대본도 함께 바뀐다.', '> 말하는 속도 분당 약 300자 기준, 파트당 3~4분. "보충" 슬라이드는 질문이 나올 때만 쓴다.', ''];
  let cur = null;
  for (const x of SCRIPT) {
    const sec = x.title && x.title.startsWith('보충') ? '보충 (질문용)' : x.part ? `파트 ${PART[x.part][0]} ${PART[x.part][1]}` : '도입·마무리';
    if (sec !== cur) { md.push('', `## ${sec}`, ''); cur = sec; }
    md.push(`**[${x.no}쪽 — ${x.title}]** (약 ${Math.round(x.text.length / 300 * 60)}초)`, x.text, '');
  }
  md.push('## 예상 질문과 답', '',
    `- **"태양광 오차가 6.05%인가요, 6.04%인가요? 실제 하루 전에도 그 정도인가요?"** → 6.05%는 3회 평균, 6.04%는 기상 입력 비교의 단일 실행입니다. 둘 다 관측 기상입니다. 전날 14시 가정 모델은 ${f2(SI.lightgbm.nRMSE)}%였고, 실제 예보를 넣은 성능은 아직 측정하지 않았습니다.`,
    '- **"공식 예측보다 우리 모델이 낮으면 더 좋은 건가요?"** → 입력과 시스템이 함께 다르고 하루치라 판단할 수 없습니다. 같은 발행 시각 정보로 비교해야 합니다.',
    '- **"80% 범위면 내일도 80%가 들어오나요?"** → 2024년 전체에서 잰 비율입니다. 같은 조건에서도 달마다 달랐습니다.',
    '- **"이상 후보는 실제 고장이었나요?"** → 정비 기록과 대조하지 못해 "후보"라고 부릅니다. 공개된 예방정비 기록은 화력·복합 설비뿐이었습니다.',
    `- **"원전 상관 ${f2(NO.corr_outage_days_vs_cf)}이면 AI로 정비 기간을 줄일 수 있나요?"** → 정비가 긴 해에 이용률이 낮은 경향을 보여 줄 뿐입니다. 줄일 수 있는지는 설비 상태 자료로 따로 시험해야 합니다.`,
    '- **"풍력은 왜 0건인가요?"** → 바람 때문에 매일 출렁여 발전량만으로는 드러나지 않습니다. 풍속과 함께 보거나 같은 단지 호기끼리 비교해야 합니다.', '');
  fs.writeFileSync(path.join(E, 'report/발표대본.md'), md.join('\n'));
  console.log('wrote', out, 'slides', slideNo, '+ report/발표대본.md');
})();
