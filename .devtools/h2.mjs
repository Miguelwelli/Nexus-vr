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
console.log(JSON.stringify(await page.evaluate(async () => {
  NX.hands.setEnabled(true);
  await new Promise(r => setTimeout(r, 900));
  const bg = NX.scene.scene3.children.filter(c => c.type === 'Group');
  return { ready: NX.hands.ready, groupNames: bg.map(g => g.name),
           scaledGroupSizes: bg.map(g => [g.scale.x, g.children.length]),
           sceneChildren: NX.scene.scene3.children.length };
}), null, 1));
await browser.close();
