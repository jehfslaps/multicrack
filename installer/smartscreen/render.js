// node installer/smartscreen/render.js <out.png>   (needs playwright)
const path = require('path');
const { chromium } = require('playwright');
(async () => {
  const out = path.resolve(process.argv[2] || 'Windows warning - how to install.png');
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1 });
  await p.goto('file://' + path.join(__dirname, 'guide.html'));
  await p.evaluate(() => document.fonts.ready);
  await p.waitForTimeout(200);
  await p.screenshot({ path: out });
  await b.close();
  console.log(out);
})();
