// D-1 (answer 73): the homepage copy's NEW live layer site/assets/ais_api_live.js against a REAL local backend (uvicorn, SQLite, PROVIDER_MODE=mock, RENDER3D_ENABLED=true).
// Real: the static site files, Chromium, the real HTTP API (renders, library, video job, GLB export). Not real: login (a bearer token of the harness user), any AI model.
// The site's own pages do not load the live file yet (the design window merges it); this flow injects it into the 3D studio page, as the merge will.
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { createReadStream, existsSync, statSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, extname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { tmpdir } from 'node:os';
import { chromium, startStack, USERS } from './harness.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const SITE = resolve(here, '..', '..', 'site');
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.webp': 'image/webp', '.woff2': 'font/woff2' };
const SITE_PORT = 4782;
const ORIGIN = `http://127.0.0.1:${SITE_PORT}`;
const OUT = process.env.E2E_OUT || join(tmpdir(), 'd1-3d-live');
mkdirSync(OUT, { recursive: true });

const web = createServer((req, res) => {
  const path = decodeURIComponent((req.url || '/').split('?')[0]);
  const file = join(SITE, path === '/' ? 'index.html' : path);
  if (!file.startsWith(SITE) || !existsSync(file) || statSync(file).isDirectory()) { res.writeHead(404); return res.end('not found'); }
  res.writeHead(200, { 'Content-Type': MIME[extname(file)] || 'application/octet-stream' }); createReadStream(file).pipe(res);
}).listen(SITE_PORT, '127.0.0.1');

const stack = await startStack({ apiPort: 8790, webPort: 4790, extraEnv: { RENDER3D_ENABLED: 'true', APP_CORS_ORIGINS: ORIGIN, RENDER3D_DAILY_LIMIT: '50' } });
const results = [];
const run = async (name, fn) => {
  const t = Date.now();
  try { await fn(); results.push({ name, ok: true }); console.log(`PASS  ${name} (${Date.now() - t} ms)`); }
  catch (e) { results.push({ name, ok: false }); console.log(`FAIL  ${name}\n      ${String(e && e.message || e).split('\n').slice(0, 6).join('\n      ')}`); }
};

// page.evaluate shows a thrown plain object as "Object": carry it through as JSON text so a failure says WHAT the server answered
const live = (fn, arg) => page.evaluate(async ([src, a]) => { try { return await (0, eval)('(' + src + ')')(a); } catch (e) { throw new Error('LIVE ' + JSON.stringify(e && e.code ? e : String(e && e.message || e))); } }, [fn.toString(), arg]);
const auth = { Authorization: `Bearer ${USERS.owner.token}` };
const WS = 'ws-live-3d';
const created = await fetch(`${stack.apiUrl}/v1/workspaces`, { method: 'POST', headers: { ...auth, 'Content-Type': 'application/json' }, body: JSON.stringify({ workspace_id: WS }) });
assert.equal(created.status, 201, 'workspace created');

let page;
const browser = await chromium.launch();
let timings = {};
try {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await context.route(url => !/^(http:\/\/127\.0\.0\.1|data:|blob:)/.test(url.href), route => route.abort());      // hermetic
  page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e.message || e).slice(0, 300)));
  await page.goto(`${ORIGIN}/ko/studio-3d.html`);
  await page.addScriptTag({ url: `${ORIGIN}/assets/ais_api_live.js` });
  const configure = () => page.evaluate(([base, token, ws]) => AIS_LIVE.configure({ base, token: () => token, workspaceId: ws }), [stack.apiUrl, USERS.owner.token, WS]);

  await run('not configured, or the server unreachable: every call answers null (the screen keeps its local behaviour), no error', async () => {
    const r = await page.evaluate(async () => [await AIS_API.studio3d.poses(), await AIS_API.studio3d.render({ sex: 'female', garments: ['top'] }), await AIS_API.studio3d.fitCheck({ sex: 'female', kind: 'top' })]);
    assert.deepEqual(r, [null, null, null]);
    await page.evaluate(() => AIS_LIVE.configure({ base: 'http://127.0.0.1:1', token: 'x', workspaceId: 'w' }));
    assert.equal(await page.evaluate(() => AIS_API.studio3d.poses()), null);
    assert.equal(await page.evaluate(() => AIS_LIVE.ping()), false);
  });

  await run('configured: ping is true and poses() lists the five M5 poses', async () => {
    assert.equal(await configure(), true);
    assert.equal(await page.evaluate(() => AIS_LIVE.ping()), true);
    const poses = await page.evaluate(() => AIS_API.studio3d.poses());
    assert.deepEqual(poses.map(p => p.id), ['standing', 'walking', 'hand_on_hip', 'sitting', 'arms_raised']);
  });

  await run('fitCheck() returns S/M/L margins and a recommendation (section 15)', async () => {
    const r = await page.evaluate(() => AIS_API.studio3d.fitCheck({ sex: 'female', kind: 'top' }));
    assert.deepEqual(Object.keys(r.sizes).sort(), ['L', 'M', 'S']);
    assert.ok(['S', 'M', 'L', null].includes(r.recommended) && r.limits.source === 'proposal');
    await assert.rejects(page.evaluate(() => AIS_API.studio3d.fitCheck({ sex: 'female', kind: 'top', measurements: { chest_cm: 5 } }).catch(e => { throw new Error(e.code); })), /FIT_CHECK_INVALID|RENDER3D_MEASUREMENT_INVALID|fit/i);
  });

  const stills = {};
  await run('render(): model + 2 garments + a pose + 5 angles -> five real pictures from the server (lit renderer)', async () => {
    const t0 = Date.now();
    const r = await live(() => AIS_API.studio3d.render({ modelId: 'mf0', garments: ['top', 'bottom'], pose: 'walking', angles: [0, 45, 90, 180, 270], renderer: 'photo' }));
    timings.photo5 = Date.now() - t0;
    assert.equal(r.images.length, 5);
    assert.deepEqual(r.images.map(i => i.angle), [0, 45, 90, 180, 270]);
    assert.ok(r.qc.passed && r.pose === 'walking' && r.renderer === 'photo');
    const info = await page.evaluate(async imgs => Promise.all(imgs.map(async im => { const img = new Image(); img.src = im.url; await img.decode(); const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; const g = c.getContext('2d'); g.drawImage(img, 0, 0); const d = g.getImageData(0, 0, c.width, c.height).data; let min = 255, max = 0; for (let i = 0; i < d.length; i += 4) { const v = d[i] + d[i + 1] + d[i + 2]; if (v < min) min = v; if (v > max) max = v; } return { w: img.width, h: img.height, spread: (max - min) / 3, url: c.toDataURL('image/png') }; })), r.images);
    assert.ok(info.every(i => i.w === 360 && i.h === 640 && i.spread > 40), 'each picture is a real, non-flat image');
    stills.after = info.map(i => i.url);
    stills.assets = r.images;
  });

  await run('render(): the fast mock renderer in the standing pose gives the "before" pictures; both differ', async () => {
    const t0 = Date.now();
    const r = await live(() => AIS_API.studio3d.render({ sex: 'female', garments: ['top', 'bottom'], pose: 'standing', angles: [0, 90], renderer: 'soft' }));
    timings.soft2 = Date.now() - t0;
    assert.equal(r.images.length, 2);
    stills.before = await page.evaluate(async imgs => Promise.all(imgs.map(async im => { const img = new Image(); img.src = im.url; await img.decode(); const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; c.getContext('2d').drawImage(img, 0, 0); return c.toDataURL('image/png'); })), r.images);
    for (const [i, name] of ['before_front', 'before_side'].entries()) writeFileSync(join(OUT, `d1_${name}.png`), Buffer.from(stills.before[i].split(',')[1], 'base64'));
    for (const [i, a] of [0, 45, 90, 180, 270].entries()) writeFileSync(join(OUT, `d1_after_${a}.png`), Buffer.from(stills.after[i].split(',')[1], 'base64'));
    assert.notEqual(stills.before[0], stills.after[0]);
  });

  let itemIds = [];
  await run('saveToLibrary(): the five pictures become render items of the workspace library', async () => {
    const items = await page.evaluate(imgs => AIS_API.studio3d.saveToLibrary(imgs, { name: '3D 촬영' }), stills.assets.map(a => ({ asset_id: a.asset_id, angle: a.angle })));
    assert.equal(items.length, 5);
    itemIds = items.map(i => i.item_id);
    const list = await (await fetch(`${stack.apiUrl}/v1/workspaces/${WS}/library?kind=render`, { headers: auth })).json();
    assert.ok(list.total >= 5);
  });

  await run('toVideo(): the saved pictures go to a video job (library item -> video) and it succeeds', async () => {
    const job = await live(ids => AIS_API.studio3d.toVideo({ itemIds: ids.slice(0, 3), aspect: '9:16', duration: 6 }), itemIds);
    assert.equal(job.status, 'succeeded', JSON.stringify(job).slice(0, 300));
  });

  await run('export(): a stored GLB comes back with its provenance block and a matching hash (section 14)', async () => {
    const doc = Buffer.from(JSON.stringify({ asset: { version: '2.0' } }));
    const pad = Buffer.concat([doc, Buffer.alloc((4 - doc.length % 4) % 4, 0x20)]);
    const head = Buffer.alloc(12); head.write('glTF', 0); head.writeUInt32LE(2, 4); head.writeUInt32LE(12 + 8 + pad.length, 8);
    const ch = Buffer.alloc(8); ch.writeUInt32LE(pad.length, 0); ch.writeUInt32LE(0x4E4F534A, 4);
    const glb = Buffer.concat([head, ch, pad]);
    const form = new FormData(); form.append('workspace_id', WS); form.append('file', new Blob([glb], { type: 'model/gltf-binary' }), 'chair.glb');
    const up = await fetch(`${stack.apiUrl}/v1/assets`, { method: 'POST', headers: auth, body: form });
    assert.equal(up.status, 201, await up.clone().text());
    const assetId = (await up.json()).asset_id;
    const r = await page.evaluate(async id => { const x = await AIS_API.studio3d.export({ assetId: id, format: 'glb' }); const buf = new Uint8Array(await x.blob.arrayBuffer()); return { sha: x.sha256, bytes: x.bytes, magic: String.fromCharCode(...buf.slice(0, 4)), text: new TextDecoder().decode(buf), name: x.filename }; }, assetId);
    assert.equal(r.magic, 'glTF');
    assert.ok(r.text.includes('acs_export') && r.sha && r.sha.length === 64 && r.name.endsWith('.glb'));
  });

  assert.deepEqual(errors, [], 'no script error on the page');
} finally {
  await browser.close();
  await stack.stop();
  web.close();
}
console.log(`TIMINGS (this machine, CI runner) photo 5 angles + 2 garments + pose: ${timings.photo5} ms; soft 2 angles: ${timings.soft2} ms; pictures in ${OUT}`);
const passed = results.filter(r => r.ok).length;
console.log(`SUMMARY ${passed}/${results.length} live 3D steps passed`);
process.exit(passed === results.length ? 0 : 1);
