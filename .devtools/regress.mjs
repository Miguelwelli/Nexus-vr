import { chromium } from 'playwright-core';
import sparticuz from '@sparticuz/chromium';
const execPath = await sparticuz.executablePath();
const browser = await chromium.launch({ executablePath: execPath, args: [...sparticuz.args,'--no-sandbox','--autoplay-policy=no-user-gesture-required'], headless: true });
const results = [];
for (const [w,h,label] of [[430,932,'portrait'],[1024,768,'landscape']]) {
  const page = await browser.newPage({ viewport: { width: w, height: h } });
  const errs = [];
  page.on('pageerror', e => errs.push('ERR ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errs.push('CONSOLE ' + m.text()); });
  page.on('requestfailed', r => errs.push('404 ' + r.url().split('/').pop()));
  await page.goto('http://127.0.0.1:5173/', { waitUntil: 'load' });
  await page.waitForFunction(() => window.NX?.app?.booted);
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `/tmp/final-${label}-entry.png` });
  await page.click('#btn-enter');
  await page.waitForTimeout(9000);
  await page.screenshot({ path: `/tmp/final-${label}-hub.png` });

  const probe = await page.evaluate(async () => {
    const out = { worlds: {}, checks: {} };
    out.checks.boot = NX.app.booted;
    out.checks.items = NX.scene.items.length;
    out.checks.fps = Math.round(NX.app.fps);
    // cycle worlds
    for (const w of ['night','space','beach','cinema','virtual']) {
      await NX.app.setWorld(w);
      await new Promise(r => setTimeout(r, 350));
      out.worlds[w] = NX.scene.worldId === w;
    }
    await NX.app.setWorld('night');
    // settings
    NX.app.openSettings();
    await new Promise(r => setTimeout(r, 300));
    out.checks.settingsOpen = !document.getElementById('panel-settings').hidden;
    out.checks.settingsControls = document.querySelectorAll('#settings-body button, #settings-body input').length;
    NX.app.closeSettings();
    // carousel
    NX.scene.stepCard(1); NX.scene.stepCard(1); NX.scene.stepCard(-1);
    out.checks.focus = NX.scene.focusedIndex();
    // stereo
    NX.app.setStereo(true, true);
    await new Promise(r => setTimeout(r, 400));
    out.checks.stereo = NX.scene.stereo && !!document.querySelector('.vr-divider');
    NX.app.setStereo(false, true);
    // games
    for (const g of ['asteroids','orbs','neon']) {
      NX.games.begin(g);
      await new Promise(r => setTimeout(r, 500));
      out.checks['game_' + g] = NX.games.active === g;
      NX.games.quit();
      await new Promise(r => setTimeout(r, 300));
    }
    // player
    NX.player.open('assets/video/space.mp4', 'Test');
    await new Promise(r => setTimeout(r, 1500));
    out.checks.player = NX.player.opened && NX.player.video && NX.player.video.readyState >= 2;
    NX.player.close();
    await new Promise(r => setTimeout(r, 500));
    // back to entry
    document.getElementById('btn-back').click();
    await new Promise(r => setTimeout(r, 1200));
    out.checks.backToEntry = NX.app.mode === 'entry';
    return out;
  });
  results.push({ label, errs: [...new Set(errs)], probe });
  await page.close();
}
console.log(JSON.stringify(results, null, 1));
await browser.close();
