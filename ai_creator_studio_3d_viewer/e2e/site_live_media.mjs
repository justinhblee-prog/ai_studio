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

  // ---------- D-5 PSD at the ORIGINAL resolution ----------
  const big = makePng(480, 360, [90, 140, 200]);
  const formBig = new FormData(); formBig.append('workspace_id', WS); formBig.append('rights_confirmed', 'true'); formBig.append('file', new Blob([big], { type: 'image/png' }), 'photo.png');
  const upBig = await fetch(`${stack.apiUrl}/v1/assets/images`, { method: 'POST', headers: auth, body: formBig });
  assert.equal(upBig.status, 201);
  const bigId = (await upBig.json()).asset_id;
  let psdBytes = null;

  await run('photo.psdExport(): the stored photo comes back as a layered PSD at its ORIGINAL size (480x360), hash matches, 4 layers', async () => {
    const r = await live(id => AIS_API.photo.psdExport({ assetId: id }).then(async x => { const buf = new Uint8Array(await x.blob.arrayBuffer()); const h = await crypto.subtle.digest('SHA-256', buf); return { sha: x.sha256, calc: [...new Uint8Array(h)].map(b => b.toString(16).padStart(2, '0')).join(''), magic: String.fromCharCode(...buf.slice(0, 4)), width: new DataView(buf.buffer).getUint32(18), height: new DataView(buf.buffer).getUint32(14), bytes: buf.length, name: x.filename, all: Array.from(buf) }; }), bigId);
    assert.equal(r.magic, '8BPS'); assert.equal(r.width, 480); assert.equal(r.height, 360);
    assert.equal(r.sha, r.calc); assert.ok(r.name.endsWith('.psd'));
    psdBytes = Buffer.from(r.all);
    assert.ok(psdBytes.length > 1000);
  });

  await run('photo.psdImport(): the edited PSD goes back as a NEW original asset (PSD 수정본 trail) with its layers counted', async () => {
    const r = await live(arr => AIS_API.photo.psdImport({ file: new File([new Uint8Array(arr)], '수정본.psd'), rightsConfirmed: true }).then(x => ({ source: x.source, layers: x.psd.layers, names: x.psd.layer_names, reduced: x.reduced, work: x.work_size, id: x.asset.asset_id, url: !!x.url })), Array.from(psdBytes));
    assert.equal(r.layers, 4); assert.ok(r.names.some(n => n.includes('피사체'))); assert.equal(r.source, 'merged'); assert.equal(r.reduced, false);
    assert.deepEqual(r.work, [480, 360]); assert.notEqual(r.id, bigId); assert.ok(r.url);
  });

  await run('photo.psdExport()/psdImport(): an unreachable server answers null; and a non-PSD upload is refused with PSD_NOT_PSD', async () => {
    assert.equal(await page.evaluate(() => { AIS_LIVE.configure({ base: 'http://127.0.0.1:1', token: 'x', workspaceId: 'w' }); return AIS_API.photo.psdExport({ assetId: 'ast_x' }); }), null);
    await page.evaluate(([base, token, ws]) => AIS_LIVE.configure({ base, token: () => token, workspaceId: ws }), [stack.apiUrl, USERS.owner.token, WS]);
    await assert.rejects(live(() => AIS_API.photo.psdImport({ file: new File([new Uint8Array([1, 2, 3])], 'x.psd'), rightsConfirmed: true })), /PSD_NOT_PSD/);
  });

  // ---------- D-6 team board ----------
  for (const [id, role] of [[USERS.editor.id, 'editor'], [USERS.viewer.id, 'viewer']]) {
    const r = await fetch(`${stack.apiUrl}/v1/workspaces/${WS}/members`, { method: 'POST', headers: { ...auth, 'Content-Type': 'application/json' }, body: JSON.stringify({ user_id: id, role }) });
    assert.equal(r.status, 201, await r.clone().text());
  }
  const as = who => page.evaluate(([base, token, ws]) => AIS_LIVE.configure({ base, token: () => token, workspaceId: ws }), [stack.apiUrl, who.token, WS]);
  let mine, theirs;

  await run('team.create()/list(): jobs are written in the screen\'s own fields (t,w,u,st,due,cm); the owner sees all, an editor only their own', async () => {
    await as(USERS.editor);
    mine = await live(() => AIS_API.team.create({ workroom: 'photo', title: '촬영 A', due: new Date(Date.now() + 5 * 3600e3).toISOString() }));
    assert.deepEqual([mine.t, mine.w, mine.u, mine.st, mine.cm], ['촬영 A', 'photo', USERS.editor.id, 'draft', 0]);
    await as(USERS.owner);
    theirs = await live(() => AIS_API.team.create({ workroom: 'video', title: '영상 B' }));
    const all = await live(() => AIS_API.team.list({}));
    assert.deepEqual(all.items.map(i => i.t).sort(), ['영상 B', '촬영 A']);
    assert.deepEqual((await live(() => AIS_API.team.list({ workroom: 'video' }))).items.map(i => i.t), ['영상 B']);
    await as(USERS.editor);
    assert.deepEqual((await live(() => AIS_API.team.list({}))).items.map(i => i.t), ['촬영 A']);
  });

  await run('team.transition()/comment(): review, a note is REQUIRED to ask for changes, comments are counted (cm), history is kept', async () => {
    await as(USERS.editor);
    await live(id => AIS_API.team.transition(id, 'review'), mine.id);
    await as(USERS.owner);
    await assert.rejects(live(id => AIS_API.team.transition(id, 'changes'), mine.id), /JOB_NOTE_REQUIRED/);
    const changed = await live(id => AIS_API.team.transition(id, 'changes', '색을 바꿔 주세요'), mine.id);
    assert.equal(changed.st, 'changes');
    await live(id => AIS_API.team.comment(id, '확인했어요'), mine.id);
    const one = await live(id => AIS_API.team.get(id), mine.id);
    assert.equal(one.cm, 1); assert.deepEqual(one.events.map(e => e.to), ['draft', 'review', 'changes']); assert.equal(one.comments[0].body, '확인했어요');
    await as(USERS.editor);
    await assert.rejects(live(id => AIS_API.team.transition(id, 'review'), theirs.id), /FORBIDDEN/);        // an editor cannot move someone else's job (a valid step, the wrong person)
  });

  await run('team.bulk()/summary(): bulk results per job (part may fail), the weekly summary counts members, statuses and jobs due within 24 h', async () => {
    await as(USERS.owner);
    const r = await live(ids => AIS_API.team.bulk(ids, 'review'), [theirs.id, mine.id, 'job_nope']);
    const byId = Object.fromEntries(r.results.map(x => [x.id, x]));
    assert.equal(byId[theirs.id].ok, true); assert.equal(byId.job_nope.error_code, 'NOT_FOUND');
    assert.equal(byId[mine.id].ok, true);                                            // "changes" -> "review": an owner/admin may move any job
    const s = await live(() => AIS_API.team.summary('week'));
    assert.ok(s.members.some(m => m.user_id === USERS.editor.id && m.jobs === 1));
    assert.equal(s.due_soon_24h, 1);
    assert.ok(s.members.every(m => m.credits_used === null));
    await as(USERS.editor);
    assert.equal(await live(() => AIS_API.team.summary('week').then(() => 'allowed').catch(e => e.code)), 'FORBIDDEN');
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
