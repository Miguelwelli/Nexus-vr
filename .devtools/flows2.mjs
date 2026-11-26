import { chromium } from 'playwright-core';
import sparticuz from '@sparticuz/chromium';
const execPath = await sparticuz.executablePath();
const browser = await chromium.launch({ executablePath: execPath, args: [...sparticuz.args,'--no-sandbox'], headless: true });
const page = await browser.newPage({ viewport: { width: 430, height: 932 } });
const errs = [];
page.on('pageerror', e => errs.push('ERR ' + e.message));
page.on('console', m => { if (m.type() === 'error') errs.push('CONSOLE ' + m.text()); });
page.on('requestfailed', r => errs.push('REQFAIL ' + r.url().split('/').pop()));
await page.goto('http://127.0.0.1:5173/', { waitUntil: 'load' });
await page.waitForFunction(() => window.NX?.app?.booted);
await page.click('#btn-enter');
await page.waitForTimeout(8000);

// gallery
await page.evaluate(() => NX.gallery.open());
await page.waitForTimeout(1500);
await page.screenshot({ path: '/tmp/gallery.png' });
console.log('gallery:', await page.evaluate(() => ({ modal: !document.getElementById('overlay-root').hidden, choices: document.querySelectorAll('#overlay-root button').length })));
await page.evaluate(() => NX.app.closeModal());
await page.waitForTimeout(800);

// browser destinations
await page.evaluate(() => NX.browser.open('navegador'));
await page.waitForTimeout(1200);
await page.screenshot({ path: '/tmp/browser.png' });
console.log('browser:', await page.evaluate(() => ({ choices: document.querySelectorAll('#overlay-root button').length, title: document.querySelector('#overlay-root h3, #overlay-root .modal__title')?.textContent })));
await page.evaluate(() => NX.app.closeModal());
await page.waitForTimeout(600);

// hands: enable and push a synthetic native payload
const hands = await page.evaluate(async () => {
  NX.hands.setEnabled(true);
  await new Promise(r => setTimeout(r, 400));
  const joints = {};
  ['wrist','thumbTip','indexTip','middleTip','indexKnuckle','middleKnuckle','indexIntermediate','middleIntermediate','indexMetacarpal','middleMetacarpal'].forEach((name, i) => {
    joints[name] = { x: 0.10 + i * 0.004, y: -0.10 + i * 0.006, z: -0.34 };
  });
  window.dispatchEvent(new CustomEvent('nexus-xr-hands', { detail: { left: { joints }, right: { joints } } }));
  await new Promise(r => setTimeout(r, 900));
  return { enabled: NX.hands.setEnabled && true, stats: NX.hands.stats() };
});
console.log('hands:', JSON.stringify(hands));
await page.screenshot({ path: '/tmp/hands.png' });
console.log('ERRORS:', errs.length ? [...new Set(errs)] : 'none');
await browser.close();
