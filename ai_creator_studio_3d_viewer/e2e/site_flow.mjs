// B-12 2차: browser e2e of the HOMEPAGE copy in /site (3D studio + virtual try-on workroom), the flows the design window listed.
// Real: the static site files, its in-browser library (localStorage), three.js WebGL (software, as render_glb.mjs), Chromium.
// Not covered / mocked: login (a session is seeded in localStorage, as the site's own mock auth does), any server or AI model (the site has none
// connected: the try-on button is expected to answer with the "server not linked" notice), the catalog photos (img/cat and /_blob/ are not in the
// copy, so catalog garments have no picture - this flow asserts the flow, never that an image is non-blank).
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { createReadStream, existsSync, statSync } from 'node:fs';
import { dirname, extname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from './harness.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const SITE = resolve(here, '..', '..', 'site');
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.webp': 'image/webp', '.woff2': 'font/woff2', '.glb': 'model/gltf-binary' };
if (!existsSync(join(SITE, 'en', 'studio-3d.html'))) throw new Error('site/ is missing (see site/README.md)');

const PORT = 4781;
const web = createServer((req, res) => {
  const path = decodeURIComponent((req.url || '/').split('?')[0]);
  const file = join(SITE, path === '/' ? 'index.html' : path);
  if (!file.startsWith(SITE) || !existsSync(file) || statSync(file).isDirectory()) { res.writeHead(404); return res.end('not found'); }
  res.writeHead(200, { 'Content-Type': MIME[extname(file)] || 'application/octet-stream' }); createReadStream(file).pipe(res);
}).listen(PORT, '127.0.0.1');
const ORIGIN = `http://127.0.0.1:${PORT}`;

const SESSION = { user: { name: 'E2E', email: 'e2e@e2e.test' }, email: 'e2e@e2e.test', name: 'E2E', company: 'E2E Co', role: 'owner', verified: true };
const results = [];
const pageErrors = [];
const run = async (name, fn) => {
  const t = Date.now();
  try { await fn(); results.push({ name, ok: true }); console.log(`PASS  ${name} (${Date.now() - t} ms)`); }
  catch (e) { results.push({ name, ok: false }); console.log(`FAIL  ${name}\n      ${String(e && e.message || e).split('\n').slice(0, 6).join('\n      ')}`); }
};

const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
try {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const external = [];
  await context.route(url => !/^(http:\/\/127\.0\.0\.1|data:|blob:)/.test(url.href), route => { external.push(route.request().url()); route.abort(); });   // hermetic: nothing outside this machine
  await context.addInitScript(s => { try { if (!localStorage.getItem('ais_session')) localStorage.setItem('ais_session', JSON.stringify(s)); } catch (e) { /* storage blocked */ } }, SESSION);
  const page = await context.newPage();
  page.on('pageerror', e => pageErrors.push(String(e.message || e).slice(0, 300)));
  const $ = id => page.locator('#' + id);
  const renders = () => page.evaluate(() => AISLIB.all().filter(x => x.kind === 'render').length);

  // ---------- 3D studio ----------
  await run('3D studio opens with a session: stage, canvas, library tabs, no script error', async () => {
    await page.goto(`${ORIGIN}/en/studio-3d.html`);
    await page.locator('#lp3 .lp-tab').first().waitFor({ timeout: 20000 });
    assert.equal(await page.locator('#lp3 .lp-tab').count(), 5);
    assert.ok(await page.locator('#lp3 .lp-card').count() >= 1, 'the library lists models');
    assert.equal(await $('cv3').count(), 1);
    assert.equal(await $('msg').innerText(), '');
    assert.deepEqual(pageErrors, [], 'script errors on load: ' + pageErrors.join(' | '));
  });

  await run('change the model: female/male, look, skin, top style and top colour are applied', async () => {
    await $('fgm').click(); assert.ok(await $('fgm').evaluate(e => e.classList.contains('on'))); assert.ok(!(await $('fgf').evaluate(e => e.classList.contains('on'))));
    await $('fgf').click(); assert.ok(await $('fgf').evaluate(e => e.classList.contains('on')));
    await $('flook').selectOption('1'); await $('fskin').selectOption('1');
    assert.equal(await $('flook').inputValue(), '1'); assert.equal(await $('fskin').inputValue(), '1');
    await $('fts').selectOption('long'); assert.equal(await $('fts').inputValue(), 'long');
    await $('ftop').evaluate(e => { e.value = '#c42834'; e.dispatchEvent(new Event('input', { bubbles: true })); });
    assert.equal(await $('cc').inputValue(), '#c42834', 'the top colour is mirrored in the view panel');
  });

  await run('accessories toggle on and off; the background chip and background colour change', async () => {
    const chip = $('facs').locator('.chip').first();
    await chip.click(); assert.ok(await chip.evaluate(e => e.classList.contains('on')));
    await chip.click(); assert.ok(!(await chip.evaluate(e => e.classList.contains('on'))));
    const white = $('bgp').locator('[data-id="white"]'); await white.click(); assert.ok(await white.evaluate(e => e.classList.contains('on')));
    await $('bg').evaluate(e => { e.value = '#ffffff'; e.dispatchEvent(new Event('input', { bubbles: true })); });
    assert.equal(await $('bg').inputValue(), '#ffffff');
  });

  await run('"Save 5 angle images" fills the thumbnails, says so, and stores 5 results in the library', async () => {
    const before = await renders();
    await $('angles').evaluate(e => e.click());   // the dock hides this button, the dock's own button calls the same handler
    await page.waitForFunction(() => document.querySelectorAll('#shots .thumb').length >= 5, null, { timeout: 60000 });
    await page.waitForFunction(() => /Saved 5 angle images/.test(document.getElementById('msg').textContent), null, { timeout: 20000 });
    await page.waitForFunction(b => AISLIB.all().filter(x => x.kind === 'render').length >= b + 5, before, { timeout: 20000 });
    assert.equal(await page.locator('#shots .thumb').count(), 5);
    assert.equal((await renders()) - before, 5);
  });

  await run('"Save this view as an image" adds one more thumbnail and confirms', async () => {
    await $('shot').evaluate(e => e.click());
    await page.waitForFunction(() => document.querySelectorAll('#shots .thumb').length === 6, null, { timeout: 20000 });
    assert.match(await $('msg').innerText(), /Saved\./);
  });

  await run('picking a photo model from the library shows its photo card on the stage', async () => {
    await page.locator('#lp3 .lp-card').first().click();
    await page.locator('#phRef').waitFor({ timeout: 10000 });
    assert.match(await $('wbpick').innerText(), /Picked/);
  });

  // ---------- virtual try-on workroom ----------
  await run('try-on workroom: generating with nothing picked asks for a model and a garment', async () => {
    await page.goto(`${ORIGIN}/en/tryon-studio.html`);
    await page.locator('#lpmount .lp-tab').first().waitFor({ timeout: 20000 });
    await $('go').click();
    assert.match(await $('msg').innerText(), /Pick both a model photo and a garment photo/);
  });

  await run('try-on workroom: uploading without the rights confirmation is refused', async () => {
    await $('msg').evaluate(e => { e.textContent = ''; });
    await page.locator('#lpmount button', { hasText: 'Upload mine' }).first().click();
    assert.match(await $('msg').innerText(), /Confirm usage rights first/);
  });

  await run('try-on workroom: library model + a user garment, then "Make try-on image" answers with the server-not-linked notice', async () => {
    // the catalog garment photos are not in the site copy, so the user's own garment (the library's addUser API, as an upload would store it) is used
    await page.evaluate(() => { const c = document.createElement('canvas'); c.width = c.height = 64; const x = c.getContext('2d'); x.fillStyle = '#c42834'; x.fillRect(0, 0, 64, 64); AISLIB.addUser('garment', 'E2E tee', c.toDataURL('image/png'), { type: 'Top', shape: 'tee' }); });
    await page.goto(`${ORIGIN}/en/tryon-studio.html`);
    const tab = name => page.locator('#lpmount .lp-tab').filter({ hasText: name });
    await tab('Models').click(); await page.locator('#lpmount .lp-card').first().click();
    await page.waitForFunction(() => !document.getElementById('pm').hidden, null, { timeout: 15000 });
    await tab('Clothing').click(); await page.locator('#lpmount .lp-card', { hasText: 'E2E tee' }).click();
    await page.waitForFunction(() => !document.getElementById('pg').hidden, null, { timeout: 15000 });
    await $('go').click();
    await page.waitForFunction(() => /works once the server/.test(document.getElementById('msg').textContent), null, { timeout: 15000 });
    const last = await page.evaluate(() => JSON.parse(localStorage.getItem('ais_usage') || '[]').pop());
    assert.equal(last.service, 'tryon'); assert.equal(last.status, 'blocked');
    assert.equal(await $('resbox').evaluate(e => e.hidden), true, 'no result is shown without a server');
  });

  await run('nothing left this machine, and no script error on either screen', async () => {
    assert.deepEqual(pageErrors, [], 'script errors: ' + pageErrors.join(' | '));
    console.log(`      blocked outside requests: ${external.length}`);
  });
} finally {
  await browser.close(); web.close();
}
const passed = results.filter(r => r.ok).length;
console.log(`SUMMARY ${passed}/${results.length} site steps passed`);
process.exit(passed === results.length ? 0 : 1);
