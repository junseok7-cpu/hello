// HTML → PNG 캡처: node shoot.js <html폴더> <출력폴더>
const { chromium } = require('playwright'); const fs = require('fs'); const path = require('path');
(async () => {
  const [inDir, outDir] = process.argv.slice(2);
  const b = await chromium.launch(); const pg = await b.newPage({ viewport: { width: 1560, height: 1000 } });
  for (const f of fs.readdirSync(inDir).filter(f => f.endsWith('.html')).sort()) {
    await pg.goto('file://' + path.resolve(inDir, f)); await pg.waitForTimeout(200);
    await pg.screenshot({ path: path.join(outDir, f.replace('.html', '.png')) }); console.log('wrote', f);
  }
  await b.close();
})();
