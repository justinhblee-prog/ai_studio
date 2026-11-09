// Browser E2E harness: local SQLite backend (PROVIDER_MODE=mock, no external provider) + the built web app.
// Supabase Auth is MOCKED by intercepting its HTTP calls in the browser; no real Supabase is contacted.
import { spawn, spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { mkdtempSync, rmSync, existsSync, createReadStream, statSync } from 'node:fs';
import { createServer } from 'node:http';
import { tmpdir } from 'node:os';
import { join, dirname, extname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import zlib from 'node:zlib';

const here = dirname(fileURLToPath(import.meta.url));
export const VIEWER_ROOT = resolve(here, '..');
export const BACKEND_ROOT = resolve(VIEWER_ROOT, '..', 'ai_creator_studio_backend_starter');
export const SUPABASE_URL = 'https://e2e-mock.supabase.test';
const require = createRequire(import.meta.url);
export const { chromium } = require('playwright');

export const USERS = {
  owner: { token: 'tok-owner', id: 'user-owner', email: 'owner@e2e.test' },
  editor: { token: 'tok-editor', id: 'user-editor', email: 'editor@e2e.test' },
  viewer: { token: 'tok-viewer', id: 'user-viewer', email: 'viewer@e2e.test' },
  outsider: { token: 'tok-outsider', id: 'user-outsider', email: 'outsider@e2e.test' },
};

function crc32(buf) {
  let c, crc = ~0;
  for (let n = 0; n < buf.length; n++) { c = (crc ^ buf[n]) & 0xff; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; crc = (crc >>> 8) ^ c; }
  return (~crc) >>> 0;
}
export function makePng(width, height, [r, g, b]) {
  const chunk = (type, data) => { const t = Buffer.from(type); const len = Buffer.alloc(4); len.writeUInt32BE(data.length); const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(Buffer.concat([t, data]))); return Buffer.concat([len, t, data, crc]); };
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(width, 0); ihdr.writeUInt32BE(height, 4); ihdr[8] = 8; ihdr[9] = 2;
  const row = Buffer.concat([Buffer.from([0]), Buffer.alloc(width * 3)]);
  for (let x = 0; x < width; x++) { row[1 + x * 3] = r; row[2 + x * 3] = (g + x * 3) & 255; row[3 + x * 3] = b; }
  const raw = Buffer.concat(Array.from({ length: height }, () => row));
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', ihdr), chunk('IDAT', zlib.deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]);
}

async function waitFor(url, label, ms = 30000) {
  const start = Date.now();
  for (;;) {
    try { const r = await fetch(url); if (r.ok) return; } catch { /* not up yet */ }
    if (Date.now() - start > ms) throw new Error(`${label} did not start: ${url}`);
    await new Promise(r => setTimeout(r, 250));
  }
}

const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.map': 'application/json', '.woff2': 'font/woff2' };

export async function startStack({ apiPort = 8765, webPort = 4765, extraEnv = {} } = {}) {
  const work = mkdtempSync(join(tmpdir(), 'acs-e2e-'));
  const origin = `http://127.0.0.1:${webPort}`;
  const env = {
    ...process.env, PROVIDER_MODE: 'mock', ASSET_SIGNING_SECRET: 's'.repeat(48),
    ASSET_API_TOKENS: Object.values(USERS).map(u => `${u.token}:${u.id}`).join(','),
    ASSET_STORAGE_DIR: join(work, 'private'), ASSET_DATABASE_PATH: join(work, 'app.sqlite3'),
    OUTPUT_DIR: join(work, 'outputs'), APP_CORS_ORIGINS: origin, ...extraEnv,
  };
  const api = spawn('python', ['-m', 'uvicorn', 'app.main:app', '--port', String(apiPort), '--host', '127.0.0.1'], { cwd: BACKEND_ROOT, env, stdio: ['ignore', 'pipe', 'pipe'] });
  let apiLog = ''; api.stdout.on('data', d => { apiLog += d; }); api.stderr.on('data', d => { apiLog += d; });
  const dist = join(VIEWER_ROOT, 'dist');
  if (!existsSync(join(dist, 'index.html'))) throw new Error('dist/ is missing: run the build first (see e2e/README.md)');
  const web = createServer((req, res) => {
    const path = decodeURIComponent((req.url || '/').split('?')[0]);
    let file = join(dist, path === '/' ? 'index.html' : path);
    if (!file.startsWith(dist) || !existsSync(file) || statSync(file).isDirectory()) file = join(dist, 'index.html');
    res.writeHead(200, { 'Content-Type': MIME[extname(file)] || 'application/octet-stream' }); createReadStream(file).pipe(res);
  }).listen(webPort, '127.0.0.1');
  await waitFor(`http://127.0.0.1:${apiPort}/health`, 'backend');
  return {
    apiUrl: `http://127.0.0.1:${apiPort}`, webUrl: origin, work, env, apiLog: () => apiLog,
    async stop() { api.kill('SIGTERM'); web.close(); await new Promise(r => setTimeout(r, 300)); rmSync(work, { recursive: true, force: true }); },
  };
}

// Mock Supabase Auth for one browser context. `who` selects the user returned for password logins.
export async function mockSupabase(context, who = USERS.owner) {
  const byToken = Object.values(USERS);
  await context.route(`${SUPABASE_URL}/**`, async route => {
    const url = new URL(route.request().url()); const json = (status, body) => route.fulfill({ status, contentType: 'application/json', headers: { 'access-control-allow-origin': '*' }, body: JSON.stringify(body) });
    if (route.request().method() === 'OPTIONS') return route.fulfill({ status: 204, headers: { 'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*' } });
    if (url.pathname.endsWith('/auth/v1/token') && url.searchParams.get('grant_type') === 'password') {
      return json(200, { access_token: who.token, refresh_token: 'refresh-' + who.id, expires_in: 3600, token_type: 'bearer', user: { id: who.id, email: who.email } });
    }
    if (url.pathname.endsWith('/auth/v1/user')) {
      const token = (route.request().headers().authorization || '').replace(/^Bearer /, '');
      const user = byToken.find(u => u.token === token);
      return user ? json(200, { id: user.id, email: user.email }) : json(401, { message: 'invalid token' });
    }
    if (url.pathname.endsWith('/auth/v1/logout')) return json(204, {});
    return json(404, { message: 'unmocked Supabase endpoint: ' + url.pathname });
  });
}

export async function acceptLegalThroughUi(page, { aiTraining = false } = {}) {
  const gate = page.locator('.legal-gate');
  await gate.waitFor({ timeout: 20000 });
  for (const box of await gate.locator('.legal-list input[type=checkbox]').all()) await box.check();
  if (aiTraining) await gate.locator('.legal-optional input[type=checkbox]').check();
  await gate.getByRole('button', { name: '동의하고 계속' }).click();
}

// By default a user who has not accepted the legal documents is taken through the real gate screen, so every flow
// exercises it. Pass acceptLegal: false to stop at the gate.
export async function loginThroughUi(page, webUrl, who, { beforeSubmit, acceptLegal = true } = {}) {
  await page.goto(webUrl);
  await page.getByRole('button', { name: '로그인' }).first().click();
  await page.locator('input[type=email]').waitFor();
  if (beforeSubmit) await beforeSubmit();
  await page.locator('input[type=email]').fill(who.email);
  await page.locator('input[type=password]').fill('password-123');
  await page.locator('button.auth-submit').click();
  await page.locator('.workspace-select, .legal-gate').first().waitFor({ timeout: 20000 });
  if (await page.locator('.legal-gate').count()) {
    if (!acceptLegal) return;
    await acceptLegalThroughUi(page);
  }
  await page.locator('.workspace-select').waitFor({ timeout: 20000 });
}

export function sessionSeed(who) {
  return { access_token: who.token, refresh_token: 'refresh-' + who.id, expires_at: Math.floor(Date.now() / 1000) + 3600, user: { id: who.id, email: who.email } };
}

export async function gotoPage(page, label) {
  await page.locator('button.nav', { hasText: label }).click();
}

// Minimal step runner: prints PASS/FAIL per step and returns a summary; on failure keeps page text and API log tail.
export function makeRunner(page, stack) {
  const results = [];
  const run = async (name, fn) => {
    const started = Date.now();
    try { await fn(); results.push({ name, ok: true, ms: Date.now() - started }); console.log(`PASS  ${name} (${Date.now() - started} ms)`); }
    catch (error) {
      results.push({ name, ok: false, ms: Date.now() - started, error: String(error.message || error).slice(0, 600) });
      console.log(`FAIL  ${name}\n      ${String(error.message || error).split('\n').slice(0, 6).join('\n      ')}`);
      try { console.log('      page text: ' + (await page.locator('main').innerText()).replace(/\s+/g, ' ').slice(0, 700)); } catch { /* page gone */ }
      console.log('      api log tail: ' + stack.apiLog().split('\n').slice(-6).join(' | ').slice(0, 600));
      throw error;
    }
  };
  return { run, results };
}
export const apiCall = async (stack, token, path, init = {}) => {
  const res = await fetch(stack.apiUrl + path, { ...init, headers: { Authorization: `Bearer ${token}`, ...(init.headers || {}) } });
  return { status: res.status, body: await res.json().catch(() => null) };
};

// Owner-side setup through the API: workspace with members, one image, a photo draft and one processed run.
export async function seedSharedWorkspace(stack, { withRun = true } = {}) {
  const j = (token, path, init = {}) => apiCall(stack, token, path, { ...init, headers: { 'Content-Type': 'application/json', ...(init.headers || {}) } });
  const workspace = 'ws_roles' + Math.random().toString(16).slice(2, 10);
  let r = await j(USERS.owner.token, '/v1/workspaces', { method: 'POST', body: JSON.stringify({ workspace_id: workspace }) });
  if (r.status !== 201) throw new Error('workspace seed failed ' + r.status);
  for (const [who, role] of [[USERS.editor, 'editor'], [USERS.viewer, 'viewer']]) {
    r = await j(USERS.owner.token, `/v1/workspaces/${workspace}/members`, { method: 'POST', body: JSON.stringify({ user_id: who.id, role }) });
    if (r.status !== 201) throw new Error(`member seed failed for ${role}: ${r.status} ${JSON.stringify(r.body)}`);
  }
  const form = new FormData(); form.set('workspace_id', workspace);
  form.set('rights_confirmed', 'true'); form.set('depicts_person', 'false'); form.set('likeness_consent', 'false'); // uploads must declare rights by default (D2)
  form.set('file', new Blob([makePng(48, 32, [30, 140, 60])], { type: 'image/png' }), 'seed.png');
  const up = await fetch(stack.apiUrl + '/v1/assets/images', { method: 'POST', headers: { Authorization: `Bearer ${USERS.owner.token}` }, body: form });
  if (up.status !== 201) throw new Error('image seed failed ' + up.status);
  const asset = await up.json();
  const out = { workspace, assetId: asset.asset_id };
  if (withRun) {
    r = await j(USERS.owner.token, '/v1/photo-drafts', { method: 'POST', body: JSON.stringify({ workspace_id: workspace, source_asset_id: asset.asset_id, operation: 'ENHANCE', preserve_identity: true, preserve_product_geometry: true, preserve_text_and_logo: true, output_format: 'PNG', output_count: 1 }) });
    if (r.status !== 201) throw new Error('draft seed failed ' + r.status + JSON.stringify(r.body));
    out.draftId = r.body.draft_id;
    r = await j(USERS.owner.token, `/v1/photo-drafts/${out.draftId}/process-local?workspace_id=${workspace}`, { method: 'POST', headers: { 'Idempotency-Key': 'seed-' + workspace }, body: JSON.stringify({}) });
    if (r.status !== 200) throw new Error('process seed failed ' + r.status + JSON.stringify(r.body));
    const runs = await j(USERS.owner.token, `/v1/photo-drafts/${out.draftId}/runs?workspace_id=${workspace}`);
    out.runId = (runs.body.items || runs.body.runs)[0].run_id;
  }
  return out;
}

export async function newUserPage(browser, who, { viewport } = {}) {
  const context = await browser.newContext({ acceptDownloads: true, ...(viewport ? { viewport } : {}) });
  await mockSupabase(context, who);
  const page = await context.newPage();
  page.on('dialog', d => d.accept());
  return { context, page };
}

export function sqliteExec(stack, sql, params = []) {
  const r = spawnSync('python', ['-c', 'import sqlite3,sys,json;db=sqlite3.connect(sys.argv[1]);db.execute(sys.argv[2],json.loads(sys.argv[3]));db.commit()', stack.env.ASSET_DATABASE_PATH, sql, JSON.stringify(params)], { encoding: 'utf8' });
  if (r.status !== 0) throw new Error('sqlite failed: ' + r.stderr);
}

// The mock provider never produces an image, so a finished job output is seeded the way the backend unit tests do it
// (see seed_job_output.py). The real provider path is not exercised by this.
export function seedFinishedJobOutput(stack, jobId) {
  const r = spawnSync('python', [resolve(here, 'seed_job_output.py'), jobId], { cwd: BACKEND_ROOT, env: { ...stack.env, PYTHONPATH: BACKEND_ROOT }, encoding: 'utf8', timeout: 60000 });
  if (r.status !== 0) throw new Error('seeding the job output failed: ' + (r.stderr || r.stdout).slice(-600));
}
