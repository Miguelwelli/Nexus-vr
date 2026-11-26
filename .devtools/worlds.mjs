import { chromium } from 'playwright-core';
import sparticuz from '@sparticuz/chromium';
const execPath = await sparticuz.executablePath();
const browser = await chromium.launch({ executablePath: execPath, args: [...sparticuz.args,'--no-sandbox'], headless: true });
const page = await browser.newPage({ viewport: { width: 1024, height: 768 } });
const errs = [];
page.on('pageerror', e => errs.push('ERR ' + e.message));
page.on('console', m => { if (m.type() === 'error') errs.push('CONSOLE ' + m.text()); });
await page.goto('http://127.0.0.1:5173/', { waitUntil: 'load' });
await page.waitForFunction(() => window.NX?.app?.booted);
await page.click('#btn-enter');
await page.waitForTimeout(8000);
for (const w of ['night','space','beach','cinema','virtual']) {
  await page.evaluate(id => NX.app.setWorld(id), w);
  await page.waitForTimeout(4500);
  await page.screenshot({ path: `/tmp/world-${w}.png` });
  console.log(w, JSON.stringify(await page.evaluate(() => ({ world: NX.scene.worldId, sky: !!NX.scene.sky, map: !!(NX.scene.sky && NX.scene.sky.material.map) }))));
}
console.log('ERRORS:', errs.length ? [...new Set(errs)] : 'none');
await browser.close();
