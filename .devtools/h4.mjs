import { chromium } from 'playwright-core';
import sparticuz from '@sparticuz/chromium';
const execPath = await sparticuz.executablePath();
const browser = await chromium.launch({ executablePath: execPath, args: [...sparticuz.args,'--no-sandbox'], headless: true });
const page = await browser.newPage({ viewport: { width: 430, height: 932 } });
page.on('pageerror', e => console.log('ERR', e.message));
await page.goto('http://127.0.0.1:5173/', { waitUntil: 'load' });
await page.waitForFunction(() => window.NX?.app?.booted);
await page.click('#btn-enter');
await page.waitForTimeout(7000);
const out = await page.evaluate(async () => {
  NX.hands.setEnabled(true);
  await new Promise(r => setTimeout(r, 800));
  const joints = { wrist: {x:0.1,y:-0.1,z:-0.42}, palm:{x:0.1,y:-0.04,z:-0.41} };
  const log = [];
  for (let i = 0; i < 6; i++) {
    window.dispatchEvent(new CustomEvent('nexus-xr-hands', { detail: { right: { joints } } }));
    await new Promise(r => setTimeout(r, 400));
    const root = NX.scene.scene3.children.find(c => c.name === 'hand-right');
    log.push({ i, vis: root.visible, src: NX.hands.source, last: +(NX.hands._lastSample||0).toFixed(1),
               now: +NX.input ? +performance.now().toFixed(0) : 0,
               enabled: NX.hands.enabled });
  }
  return log;
});
console.log(JSON.stringify(out, null, 1));
await browser.close();
