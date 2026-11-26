import { chromium } from 'playwright-core';
import sparticuz from '@sparticuz/chromium';

const [,, url, out, w, h, waitMs, clickSel, extraWait] = process.argv;
const execPath = await sparticuz.executablePath();
const browser = await chromium.launch({
  executablePath: execPath,
  args: [...sparticuz.args, '--no-sandbox', '--disable-setuid-sandbox'],
  headless: true,
});
const page = await browser.newPage({
  viewport: { width: parseInt(w||'430'), height: parseInt(h||'932') },
  deviceScaleFactor: 2,
});
const logs = [];
page.on('console', (m) => logs.push(`[${m.type()}] ${m.text()}`));
page.on('pageerror', (e) => logs.push(`[PAGEERROR] ${e.message}\n${(e.stack||'').split('\n').slice(0,4).join('\n')}`));
page.on('requestfailed', (r) => logs.push(`[REQFAIL] ${r.url()} :: ${r.failure()?.errorText}`));
await page.goto(url, { waitUntil: 'load', timeout: 45000 }).catch(e => logs.push('[GOTO] '+e.message));
// Wait for the app to report booted
await page.waitForFunction(() => window.NX && window.NX.app && window.NX.app.booted, { timeout: 20000 }).catch(e => logs.push('[WAIT] '+e.message));
await page.waitForTimeout(parseInt(waitMs||'1200'));
if (clickSel) {
  try { await page.click(clickSel, { timeout: 6000 }); } catch(e) { logs.push('[CLICKFAIL] '+e.message); }
  await page.waitForTimeout(parseInt(extraWait||'2500'));
}
await page.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
const info = await page.evaluate(() => ({
  mode: window.NX?.app?.mode,
  sceneReady: !!(window.NX?.scene?.ready),
  items: window.NX?.scene?.items?.length || 0,
  boot: document.getElementById('boot')?.className,
  bootDisplay: getComputedStyle(document.getElementById('boot')).display,
  world: window.NX?.scene?.worldId,
  fps: window.NX?.app?.fps?.toFixed?.(0),
})).catch(e => ({err: e.message}));
await page.screenshot({ path: out });
console.log(JSON.stringify(info));
if (logs.length) console.log(logs.slice(0,40).join('\n'));
await browser.close();
