import { chromium } from 'playwright-core';
import sparticuz from '@sparticuz/chromium';
const [,, w='430', h='932', out='/tmp/flow'] = process.argv;
const execPath = await sparticuz.executablePath();
const browser = await chromium.launch({ executablePath: execPath, args: [...sparticuz.args,'--no-sandbox'], headless: true });
const page = await browser.newPage({ viewport: { width: +w, height: +h } });
const errs = [];
page.on('pageerror', e => errs.push('ERR ' + e.message));
page.on('console', m => { if (m.type() === 'error') errs.push('CONSOLE ' + m.text()); });
page.on('requestfailed', r => errs.push('REQFAIL ' + r.url().split('/').slice(-1)[0]));
await page.goto('http://127.0.0.1:5173/', { waitUntil: 'load' });
await page.waitForFunction(() => window.NX?.app?.booted);
await page.click('#btn-enter');
await page.waitForTimeout(9000);

// 1. settings
await page.click('#btn-settings');
await page.waitForTimeout(900);
await page.screenshot({ path: `${out}-settings.png` });
console.log('settings visible:', await page.evaluate(() => !document.getElementById('panel-settings').hidden));
console.log('settings controls:', await page.evaluate(() => document.querySelectorAll('#settings-body button, #settings-body input, #settings-body select').length));
await page.keyboard.press('Escape');
await page.waitForTimeout(700);

// 2. VR stereo
await page.evaluate(() => NX.app.setStereo(true));
await page.waitForTimeout(3000);
await page.screenshot({ path: `${out}-vr.png` });
console.log('stereo:', await page.evaluate(() => ({ on: NX.scene.stereo, divider: !!document.querySelector('.vr-divider'), exit: !!document.querySelector('.vr-exit') })));
await page.evaluate(() => NX.app.setStereo(false, true));
await page.waitForTimeout(1200);

// 3. games menu
await page.evaluate(() => NX.games.openMenu());
await page.waitForTimeout(900);
await page.screenshot({ path: `${out}-games.png` });
console.log('games modal:', await page.evaluate(() => ({ overlay: !document.getElementById('overlay-root').hidden, choices: document.querySelectorAll('#overlay-root button').length })));

console.log('ERRORS:', errs.length ? errs : 'none');
await browser.close();
