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
await page.waitForTimeout(9000);
for (const id of ['asteroids','orbs','neon']) {
  await page.evaluate(i => NX.games.begin(i), id);
  await page.waitForTimeout(3500);
  await page.screenshot({ path: `/tmp/game-${id}.png` });
  const st = await page.evaluate(() => ({ active: NX.games.active, id: NX.games.activeId || null, score: NX.games.score || null }));
  console.log(id, JSON.stringify(st));
  await page.evaluate(() => NX.games.quit && NX.games.quit());
  await page.waitForTimeout(900);
}
// 360 player
const player = await page.evaluate(async () => {
  try { await NX.player.openMenu(); } catch (e) { return 'openMenu err: ' + e.message; }
  return 'ok';
});
await page.waitForTimeout(1500);
await page.screenshot({ path: '/tmp/player.png' });
console.log('player:', player, JSON.stringify(await page.evaluate(() => ({ opened: NX.player.opened, title: document.getElementById('player-title')?.textContent }))));
console.log('ERRORS:', errs.length ? errs : 'none');
await browser.close();
