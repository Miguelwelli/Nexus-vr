import { chromium } from 'playwright-core';
import sparticuz from '@sparticuz/chromium';
import fs from 'fs';
const execPath = await sparticuz.executablePath();
const browser = await chromium.launch({ executablePath: execPath, args: [...sparticuz.args,'--no-sandbox'], headless: true });
const page = await browser.newPage({ viewport: { width: 430, height: 932 } });
await page.goto('http://127.0.0.1:5173/', { waitUntil: 'load' });
await page.waitForFunction(() => window.NX?.app?.booted);
await page.click('#btn-enter');
await page.waitForTimeout(7000);
const dataUrl = await page.evaluate(() => {
  const g = NX.scene.hubGroup.children[0];
  return g.userData.mesh.material.map.image.toDataURL('image/png');
});
fs.writeFileSync('/tmp/card.png', Buffer.from(dataUrl.split(',')[1], 'base64'));
console.log('saved');
await browser.close();
