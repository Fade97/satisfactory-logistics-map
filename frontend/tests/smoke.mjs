// Smoke test of all pages against a running instance: no JS errors, core elements present.
//   node frontend/tests/smoke.mjs [http://127.0.0.1:8050]
// Browser: Playwright Chromium from ~/.cache/ms-playwright (no download).
import { chromium, devices } from 'playwright-core';
import { readdirSync } from 'node:fs';

const base = process.argv[2] || 'http://127.0.0.1:8050';
const cache = process.env.HOME + '/.cache/ms-playwright';
const dir = readdirSync(cache).filter(d => /^chromium-\d+$/.test(d)).sort().pop();
const b = await chromium.launch({ executablePath: `${cache}/${dir}/chrome-linux64/chrome`, args: ['--no-sandbox'] });
const CHECKS = [
  ['overview', '.kpi'], ['map', 'canvas'], ['production', 'table.t'], ['power', '.net'], ['logistics', 'table.t'],
  ['history', 'svg, .empty'], ['planner?item=Iron%20Plate&rate=60', '.node'], ['map?item=Iron%20Ore', '.flowbar'], ['kiosk', 'aside'],
  ['karte?ware=Iron%20Ore', '.flowbar'],   // old German URL must keep working
];
let fail = 0;
for (const [devName, dev] of [['desktop', { viewport: { width: 1400, height: 900 } }], ['phone', devices['Pixel 7']]]) {
  const ctx = await b.newContext(dev);
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(e.message));
  p.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) errs.push(m.text()); });
  for (const [page, sel] of CHECKS) {
    errs.length = 0;
    await p.goto(`${base}/#/${page}`, { waitUntil: 'networkidle' });
    const ok = await p.waitForSelector(sel, { timeout: 8000 }).then(() => true, () => false);
    if (!ok) await p.screenshot({ path: `/tmp/smoke-${devName}-${page.split('?')[0]}.png` }).catch(() => {});
    const at = ok ? '' : await p.evaluate(() => location.hash);
    // Map back after a page switch? (bug from 09-30)
    if (page === 'production') { await p.goto(`${base}/#/map`); await p.waitForTimeout(1200); }
    const w = await p.evaluate(() => innerWidth);
    const bad = !ok || errs.length || (devName === 'phone' && w > 420);
    if (bad) fail++;
    console.log(`${bad ? 'FAIL  ' : 'ok    '} ${devName.padEnd(7)} #/${page}${!ok ? ' — ' + sel + ' missing (URL ' + at + ', screenshot /tmp/smoke-' + devName + '-' + page.split('?')[0] + '.png)' : ''}${errs.length ? ' — ' + errs[0] : ''}${w > 420 && devName === 'phone' ? ' — page wider than phone (' + w + ')' : ''}`);
  }
  await ctx.close();
}
await b.close();
process.exit(fail ? 1 : 0);
