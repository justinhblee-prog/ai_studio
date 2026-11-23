// D-3.. (answer 73): the homepage copy's live layer site/assets/ais_api_live.js against a REAL local backend: couple try-on (D-3). Later steps: story video (D-4), PSD (D-5), team board (D-6), library (D-7).
// Real: static site files, Chromium, the real HTTP API. Not real: login (a harness bearer token), any AI model (the couple runner is the own3d mock).
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { createReadStream, existsSync, statSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, extname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { tmpdir } from 'node:os';
import { chromium, startStack, USERS, makePng } from './harness.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const SITE = resolve(here, '..', '..', 'site');
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.webp': 'image/webp', '.woff2': 'font/woff2' };
const SITE_PORT = 4783;
const ORIGIN = `http://127.0.0.1:${SITE_PORT}`;
const OUT = process.env.E2E_OUT || join(tmpdir(), 'live-media');
mkdirSync(OUT, { recursive: true });

const web = createServer((req, res) => {
  const path = decodeURIComponent((req.url || '/').split('?')[0]);
  const file = join(SITE, path === '/' ? 'index.html' : path);
  if (!file.startsWith(SITE) || !existsSync(file) || statSync(file).isDirectory()) { res.writeHead(404); return res.end('not found'); }
  res.writeHead(200, { 'Content-Type': MIME[extname(file)] || 'application/octet-stream' }); createReadStream(file).pipe(res);
}).listen(SITE_PORT, '127.0.0.1');

const stack = await startStack({ apiPort: 8791, webPort: 4791, extraEnv: { RENDER3D_ENABLED: 'true', APP_CORS_ORIGINS: ORIGIN, RENDER3D_DAILY_LIMIT: '50' } });
const results = [];
let page;
const run = async (name, fn) => {
  const t = Date.now();
  try { await fn(); results.push({ name, ok: true }); console.log(`PASS  ${name} (${Date.now() - t} ms)`); }
  catch (e) { results.push({ name, ok: false }); console.log(`FAIL  ${name}\n      ${String(e && e.message || e).split('\n').slice(0, 6).join('\n      ')}`); console.log('      backend log tail:\n      ' + stack.apiLog().split('\n').filter(l => /error|Error|Traceback|status":(4|5)\d\d/.test(l)).slice(-6).join('\n      ').slice(0, 1500)); }
};
const live = (fn, arg) => page.evaluate(async ([src, a]) => { try { return await (0, eval)('(' + src + ')')(a); } catch (e) { throw new Error('LIVE ' + JSON.stringify(e && e.code ? e : String(e && e.message || e))); } }, [fn.toString(), arg]);
const auth = { Authorization: `Bearer ${USERS.owner.token}` };
const WS = 'ws-live-media';
const created = await fetch(`${stack.apiUrl}/v1/workspaces`, { method: 'POST', headers: { ...auth, 'Content-Type': 'application/json' }, body: JSON.stringify({ workspace_id: WS }) });
assert.equal(created.status, 201, 'workspace created');

const browser = await chromium.launch();
const timings = {};
try {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await context.route(url => !/^(http:\/\/127\.0\.0\.1|data:|blob:)/.test(url.href), route => route.abort());
  page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e.message || e).slice(0, 300)));
  await page.goto(`${ORIGIN}/ko/studio-3d.html`);
  await page.addScriptTag({ url: `${ORIGIN}/assets/ais_api_live.js` });

  await run('not configured: couple() answers null (the screen keeps its local behaviour)', async () => {
    assert.equal(await page.evaluate(() => AIS_API.tryon.couple({ photo: 'x', slots: { a: ['top'], b: [] } })), null);
    await page.evaluate(([base, token, ws]) => AIS_LIVE.configure({ base, token: () => token, workspaceId: ws }), [stack.apiUrl, USERS.owner.token, WS]);
    assert.equal(await page.evaluate(() => AIS_LIVE.ping()), true);
  });

  // a synthetic COUPLE photo: two mannequin pictures from the server's own renderer, put side by side on one canvas
  const composeCouple = (gap) => live(async g => {
    const one = async sex => { const r = await AIS_API.studio3d.render({ sex, garments: [], angles: [0], renderer: 'soft', bg: 'studio' }); const img = new Image(); img.src = r.images[0].url; await img.decode(); return img; };
    const a = await one('female'), b = await one('male');
    const c = document.createElement('canvas'); c.width = 2 * 200 + g; c.height = 640; const x = c.getContext('2d');
    x.fillStyle = 'rgb(214,224,236)'; x.fillRect(0, 0, c.width, c.height);
    x.drawImage(a, 80, 0, 200, 640, 0, 0, 200, 640); x.drawImage(b, 80, 0, 200, 640, 200 + g, 0, 200, 640);
    const blob = await new Promise(r => c.toBlob(r, 'image/png')); blob.name = 'couple.png';
    return window.__couple = blob;
  }, gap).then(() => null);

  await run('couple(): a side-by-side couple photo + garments for both people -> a new picture from the server (own3d mock), people split and put back', async () => {
    await composeCouple(60);
    const t0 = Date.now();
    const r = await live(() => AIS_API.tryon.couple({ photo: window.__couple, rightsConfirmed: true, slots: { a: ['top', 'skirt'], b: ['jacket', 'bottom'] } }));
    timings.couple = Date.now() - t0;
    assert.ok(r.url && r.qc.overlap_px === 0 && r.qc.people.length === 2 && r.mock === true);
    const info = await page.evaluate(async url => { const img = new Image(); img.src = url; await img.decode(); const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; const g = c.getContext('2d'); g.drawImage(img, 0, 0); return { w: img.width, h: img.height, url: c.toDataURL('image/png') }; }, r.url);
    assert.ok(info.w === 460 && info.h === 640, `${info.w}x${info.h}`);
    writeFileSync(join(OUT, 'd3_couple_after.png'), Buffer.from(info.url.split(',')[1], 'base64'));
    const before = await page.evaluate(async () => { const img = new Image(); img.src = URL.createObjectURL(window.__couple); await img.decode(); const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; c.getContext('2d').drawImage(img, 0, 0); return c.toDataURL('image/png'); });
    writeFileSync(join(OUT, 'd3_couple_before.png'), Buffer.from(before.split(',')[1], 'base64'));
    assert.notEqual(before, info.url);
  });

  await run('couple(): match "same" dresses both people alike; the asked-for photo can also be an already uploaded asset id', async () => {
    const r = await live(() => AIS_API.tryon.couple({ photo: window.__couple, rightsConfirmed: true, slots: { a: ['top'], b: ['bottom'] }, match: 'same' }));
    assert.ok(r.url);
    const again = await live(id => AIS_API.tryon.couple({ photo: id, slots: { a: ['top'], b: [] } }), r.asset_id);
    assert.ok(again.url && again.asset_id !== r.asset_id);
  });

  await run('couple(): two people who overlap too much are refused with a code the screen can translate', async () => {
    await composeCouple(-120);
    await assert.rejects(live(() => AIS_API.tryon.couple({ photo: window.__couple, rightsConfirmed: true, slots: { a: ['top'], b: ['top'] } })), /COUPLE_OVERLAP_TOO_LARGE|COUPLE_PERSON_NOT_FOUND/);
  });

  // ---------- D-4 story -> video ----------
  const upIds = [];
  for (const rgb of [[200, 60, 60], [60, 200, 60], [60, 60, 200]]) {
    const form = new FormData(); form.append('workspace_id', WS); form.append('rights_confirmed', 'true'); form.append('file', new Blob([makePng(120, 160, rgb)], { type: 'image/png' }), 'scene.png');
    const up = await fetch(`${stack.apiUrl}/v1/assets/images`, { method: 'POST', headers: auth, body: form });
    assert.equal(up.status, 201, await up.clone().text());
    upIds.push((await up.json()).asset_id);
  }
  const STORY = '아침에 일어났다. 커피를 마셨다. 길을 걸었다.';

  await run('video.story(): a 3-sentence story over 3 pictures, 6 s, becomes a real MP4 with one cut and caption per sentence', async () => {
    const t0 = Date.now();
    const r = await live(([ids, story]) => AIS_API.video.story({ story, length: 6, sources: ids, aspect: '9:16', captions: 'auto' }), [upIds, STORY]);
    timings.story = Date.now() - t0;
    assert.equal(r.cuts.length, 3);
    assert.deepEqual(r.cuts.map(c => c.caption), ['아침에 일어났다.', '커피를 마셨다.', '길을 걸었다.']);
    assert.deepEqual(r.cuts.map(c => [c.start, c.end]), [[0, 2], [2, 4], [4, 6]]);
    assert.equal(r.mp4.seconds, 6); assert.equal(r.mp4.frames, 144);
    const head = await page.evaluate(async url => { const b = new Uint8Array(await (await fetch(url)).arrayBuffer()); return { size: b.length, brand: String.fromCharCode(...b.slice(4, 12)) }; }, r.url);
    assert.ok(head.size > 2000 && head.brand.startsWith('ftyp'), JSON.stringify(head));
  });

  await run('video.story(): length "auto" is 3 s per scene, and fewer pictures than sentences share a picture across scenes', async () => {
    const r = await live(([ids, story]) => AIS_API.video.story({ story, length: 'auto', sources: [ids[0]], captions: null }), [upIds, STORY]);
    assert.equal(r.mp4.seconds, 9);
    assert.deepEqual([...new Set(r.cuts.map(c => c.asset_id))], [upIds[0]]);
  });

  await run('video.story(): bad length, an AI engine and a caption list of the wrong size are refused with STORY_* codes the screen can translate', async () => {
    await assert.rejects(live(ids => AIS_API.video.story({ story: 'a. b.', length: 61, sources: ids }), upIds), /STORY_SECONDS_INVALID/);
    await assert.rejects(live(ids => AIS_API.video.story({ story: 'a. b.', length: 6, sources: ids, engine: 'ai' }), upIds), /STORY_ENGINE_CLOSED/);
    await assert.rejects(live(ids => AIS_API.video.story({ story: 'a. b.', length: 6, sources: ids, captions: ['one'] }), upIds), /STORY_CAPTIONS_INVALID/);
  });

  assert.deepEqual(errors, [], 'no script error on the page');
} finally {
  await browser.close();
  await stack.stop();
  web.close();
}
console.log(`TIMINGS (CI runner) couple job: ${timings.couple} ms; story video 6 s: ${timings.story} ms; pictures in ${OUT}`);
const passed = results.filter(r => r.ok).length;
console.log(`SUMMARY ${passed}/${results.length} live media steps passed`);
process.exit(passed === results.length ? 0 : 1);
