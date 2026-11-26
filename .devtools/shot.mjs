import { chromium } from 'playwright-core';
import sparticuz from '@sparticuz/chromium';

const url = process.argv[2] || 'http://127.0.0.1:5173/';
const out = process.argv[3] || '/tmp/shot.png';
const w = parseInt(process.argv[4] || '430');
const h = parseInt(process.argv[5] || '932');
const waitMs = parseInt(process.argv[6] || '4000');
const clickSel = process.argv[7] || null;

const execPath = await sparticuz.executablePath();
const browser = await chromium.launch({
  executablePath: execPath,
  args: [...sparticuz.args, '--no-sandbox', '--disable-setuid-sandbox', '--allow-file-access-from-files'],
  headless: true,
});
const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 2 });
const logs = [];
page.on('console', (m) => logs.push(`[${m.type()}] ${m.text()}`));
page.on('pageerror', (e) => logs.push(`[PAGEERROR] ${e.message}\n${e.stack || ''}`));
page.on('requestfailed', (r) => logs.push(`[REQFAIL] ${r.url()} :: ${r.failure()?.errorText}`));
await page.goto(url, { waitUntil: 'load', timeout: 45000 }).catch(e => logs.push('[GOTO] '+e.message));
await page.waitForTimeout(waitMs);
if (clickSel) {
  try { await page.click(clickSel, { timeout: 5000 }); } catch(e) { logs.push('[CLICKFAIL] '+e.message); }
  await page.waitForTimeout(2500);
}
const info = await page.evaluate(() => ({
  three: !!window.THREE,
  nx: !!window.NX,
  sceneReady: !!(window.NX && window.NX.scene && window.NX.scene.ready),
  canvas: !!document.querySelector('canvas'),
  boot: document.getElementById('boot')?.className,
})).catch(e => ({err: e.message}));
await page.screenshot({ path: out });
console.log(JSON.stringify(info, null, 1));
console.log(logs.slice(0, 60).join('\n'));
await browser.close();
