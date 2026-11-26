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
  await new Promise(r => setTimeout(r, 800));
  const base = { x: 0.10, y: -0.10, z: -0.42 };
  const mk = (dx, dy, dz) => ({ x: base.x + dx, y: base.y + dy, z: base.z + dz });
  const joints = {
    wrist: mk(0,0,0), palm: mk(0,0.06,0.01),
    thumbMetacarpal: mk(-0.04,0.05,0), thumbProximal: mk(-0.08,0.09,-0.02), thumbTip: mk(-0.10,0.12,-0.04),
    indexMetacarpal: mk(-0.02,0.10,0), indexProximal: mk(-0.02,0.15,-0.02), indexTip: mk(-0.02,0.21,-0.05),
    middleMetacarpal: mk(0.01,0.10,0), middleProximal: mk(0.012,0.16,-0.02), middleTip: mk(0.013,0.22,-0.05),
    ringMetacarpal: mk(0.04,0.095,0), ringProximal: mk(0.045,0.15,-0.02), ringTip: mk(0.048,0.20,-0.05),
    littleMetacarpal: mk(0.06,0.08,0), littleProximal: mk(0.07,0.12,-0.02), littleTip: mk(0.075,0.16,-0.045),
  };
  window.dispatchEvent(new CustomEvent('nexus-xr-hands', { detail: { left: { joints }, right: { joints } } }));
  await new Promise(r => setTimeout(r, 1500));
  NX.scene.render(0.016);
  const root = NX.scene.scene3.children.find(c => c.name === 'hand-left');
  const tip = root && root.children.find(c => c.name === 'tip');
  return {
    rootVis: root && root.visible,
    children: root && root.children.map(c => ({ type: c.type, vis: c.visible, pos: c.position.toArray().map(v=>+v.toFixed(2)), sc: c.scale.x })),
    near: NX.scene.camera.near, far: NX.scene.camera.far,
  };
}), null, 1));
await page.waitForTimeout(300);
await page.screenshot({ path: '/tmp/hands3.png' });
await browser.close();
