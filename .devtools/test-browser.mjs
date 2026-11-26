import { chromium } from 'playwright-core';
import sparticuz from '@sparticuz/chromium';
const execPath = await sparticuz.executablePath();
const browser = await chromium.launch({
  executablePath: execPath,
  args: [...sparticuz.args, '--no-sandbox', '--disable-setuid-sandbox'],
  headless: true,
});
const page = await browser.newPage();
await page.setContent('<h1 style="font-family:sans-serif">hello browser</h1><canvas id=c></canvas>');
console.log('TITLE OK:', await page.textContent('h1'));
console.log('WEBGL:', await page.evaluate(() => { const c=document.createElement('canvas'); const gl=c.getContext('webgl2')||c.getContext('webgl'); return gl ? gl.getParameter(gl.VERSION) : 'none'; }));
await browser.close();
