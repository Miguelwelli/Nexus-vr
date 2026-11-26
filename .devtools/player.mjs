import { chromium } from 'playwright-core';
import sparticuz from '@sparticuz/chromium';
const execPath = await sparticuz.executablePath();
const browser = await chromium.launch({ executablePath: execPath, args: [...sparticuz.args,'--no-sandbox','--autoplay-policy=no-user-gesture-required'], headless: true });
const page = await browser.newPage({ viewport: { width: 430, height: 932 } });
const errs = [];
page.on('pageerror', e => errs.push('ERR ' + e.message));
page.on('console', m => { if (m.type() === 'error') errs.push('CONSOLE ' + m.text()); });
page.on('requestfailed', r => errs.push('REQFAIL ' + r.url().split('/').slice(-1)[0]));
await page.goto('http://127.0.0.1:5173/', { waitUntil: 'load' });
await page.waitForFunction(() => window.NX?.app?.booted);
await page.click('#btn-enter');
await page.waitForTimeout(8000);

// open the player menu, then pick the first clip
await page.evaluate(() => NX.player.openMenu());
await page.waitForTimeout(1200);
await page.screenshot({ path: '/tmp/player-menu.png' });
console.log('menu choices:', await page.evaluate(() => document.querySelectorAll('#overlay-root button').length));

await page.evaluate(() => NX.player.open('assets/video/space.mp4', 'Galactic Flyby'));
await page.waitForTimeout(6000);
await page.screenshot({ path: '/tmp/player-open.png' });
console.log('player:', JSON.stringify(await page.evaluate(() => {
  const v = NX.player.video;
  return { opened: NX.player.opened, panel: !document.getElementById('panel-player').hidden,
    hasVideo: !!v, readyState: v && v.readyState, w: v && v.videoWidth, h: v && v.videoHeight,
    currentTime: v && +v.currentTime.toFixed(2), paused: v && v.paused,
    mapSet: !!(NX.player.sphere && NX.player.sphere.material.map),
    loadingHidden: document.getElementById('player-loading').classList.contains('is-hidden'),
    dockHidden: document.getElementById('dock').hidden };
})));
await page.evaluate(() => NX.player.close());
await page.waitForTimeout(1200);
console.log('after close:', JSON.stringify(await page.evaluate(() => ({ opened: NX.player.opened, panel: !document.getElementById('panel-player').hidden, dock: !document.getElementById('dock').hidden }))));
console.log('ERRORS:', errs.length ? errs : 'none');
await browser.close();
