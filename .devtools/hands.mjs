import { chromium } from 'playwright-core';
import sparticuz from '@sparticuz/chromium';
const execPath = await sparticuz.executablePath();
const browser = await chromium.launch({ executablePath: execPath, args: [...sparticuz.args,'--no-sandbox'], headless: true });
const page = await browser.newPage({ viewport: { width: 430, height: 932 } });
const errs = [];
page.on('pageerror', e => errs.push('ERR ' + e.message));
await page.goto('http://127.0.0.1:5173/', { waitUntil: 'load' });
await page.waitForFunction(() => window.NX?.app?.booted);
await page.click('#btn-enter');
await page.waitForTimeout(8000);
const r = await page.evaluate(async () => {
  NX.hands.setEnabled(true);
  await new Promise(r => setTimeout(r, 600));
  // a plausible right hand: palm ~26cm in front, slightly right and low
  const base = { x: 0.055, y: -0.115, z: -0.38 };
  const mk = (dx, dy, dz) => ({ x: base.x + dx, y: base.y + dy, z: base.z + dz });
  const joints = {
    wrist: mk(0, 0, 0),
    palm: mk(0, 0.05, 0.01),
    thumbMetacarpal: mk(-0.03, 0.04, 0.005),
    thumbProximal: mk(-0.06, 0.07, -0.01),
    thumbTip: mk(-0.075, 0.09, -0.03),
    indexMetacarpal: mk(-0.01, 0.08, 0.005),
    indexProximal: mk(-0.01, 0.12, -0.01),
    indexTip: mk(-0.01, 0.165, -0.03),
    middleMetacarpal: mk(0.01, 0.08, 0.005),
    middleProximal: mk(0.012, 0.125, -0.01),
    middleTip: mk(0.013, 0.17, -0.03),
    ringMetacarpal: mk(0.03, 0.075, 0.005),
    ringProximal: mk(0.035, 0.115, -0.012),
    ringTip: mk(0.038, 0.155, -0.032),
    littleMetacarpal: mk(0.045, 0.065, 0.005),
    littleProximal: mk(0.052, 0.10, -0.012),
    littleTip: mk(0.056, 0.135, -0.030),
  };
  window.dispatchEvent(new CustomEvent('nexus-xr-hands', { detail: { left: { joints }, right: { joints } } }));
  for (let i=0;i<8;i++){ window.dispatchEvent(new CustomEvent('nexus-xr-hands', { detail: { left: { joints }, right: { joints } } })); await new Promise(r => setTimeout(r, 400)); }
  const roots = NX.scene.scene3.children.filter(c => c.name && c.name.indexOf('hand') === 0);
  return {
    roots: roots.map(r => ({ name: r.name, vis: r.visible, kids: r.children.length,
      pos: r.position.toArray().map(v => +v.toFixed(2)) })),
    stats: NX.hands.stats(),
    roots: roots.map(r => ({ name: r.name, vis: r.visible, kids: r.children.length })),
  };
});
console.log(JSON.stringify(r, null, 1));
await page.screenshot({ path: "/tmp/hands2.png" });
console.log("ERRORS:", errs.length ? errs : "none");
await browser.close();
