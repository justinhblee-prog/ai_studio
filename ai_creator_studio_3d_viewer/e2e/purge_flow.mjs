// Deletion request -> 7-day grace -> purge, on a TEMPORARY stack only (temp database and temp folders created by startStack).
// The purge script is run with explicit temp paths and refuses to start if any path is outside the OS temp folder.
// Real: backend over HTTP, SQLite, scripts/purge_requests.py. No browser. Other users' data must stay untouched.
import assert from 'node:assert/strict';
import { existsSync, readdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve, sep } from 'node:path';
import { spawnSync } from 'node:child_process';
import { startStack, makeRunner, apiCall, makePng, sqliteExec, BACKEND_ROOT, USERS } from './harness.mjs';

const stack = await startStack({ apiPort: 8767, webPort: 4767 });
let failed = false;
const json = (token, path, init = {}) => apiCall(stack, token, path, { ...init, headers: { 'Content-Type': 'application/json', ...(init.headers || {}) } });
const tempRoot = resolve(tmpdir()) + sep;
const paths = { db: stack.env.ASSET_DATABASE_PATH, assets: stack.env.ASSET_STORAGE_DIR, outputs: stack.env.OUTPUT_DIR };
for (const [name, p] of Object.entries(paths)) {
  if (!resolve(p).startsWith(tempRoot)) { console.log(`REFUSED: ${name} (${p}) is not inside the temp folder`); await stack.stop(); process.exit(2); }
}
const purge = (...extra) => spawnSync('python', ['scripts/purge_requests.py', '--db', paths.db, '--assets-dir', paths.assets, '--outputs-dir', paths.outputs, '--grace-days', '7', ...extra],
  { cwd: BACKEND_ROOT, env: { ...stack.env, PYTHONPATH: BACKEND_ROOT }, encoding: 'utf8', timeout: 60000 });
const upload = async (token, workspace, name, color) => {
  const f = new FormData(); f.set('workspace_id', workspace); f.set('rights_confirmed', 'true');
  f.set('file', new Blob([makePng(24, 24, color)], { type: 'image/png' }), name);
  const r = await fetch(`${stack.apiUrl}/v1/assets/images`, { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: f });
  const body = await r.json().catch(() => ({}));
  assert.equal(r.status, 201, JSON.stringify(body));
  return body.asset_id;
};
const files = () => readdirSync(paths.assets);
try {
  const { run, results } = makeRunner({ locator: () => ({ innerText: async () => '' }) }, stack);
  const owner = USERS.owner.token, editor = USERS.editor.token;
  const state = { wsA: 'ws_purge_a' + Math.random().toString(16).slice(2, 6), wsB: 'ws_keep_b' + Math.random().toString(16).slice(2, 6) };

  await run('setup: two workspaces with images; the owner of A asks to delete A\'s content', async () => {
    assert.equal((await json(owner, '/v1/workspaces', { method: 'POST', body: JSON.stringify({ workspace_id: state.wsA }) })).status, 201);
    assert.equal((await json(editor, '/v1/workspaces', { method: 'POST', body: JSON.stringify({ workspace_id: state.wsB }) })).status, 201);
    state.a1 = await upload(owner, state.wsA, 'a1.png', [200, 10, 10]); state.a2 = await upload(owner, state.wsA, 'a2.png', [10, 200, 10]);
    state.b1 = await upload(editor, state.wsB, 'b1.png', [10, 10, 200]);
    assert.equal(files().length, 3);
    const req = await json(owner, '/v1/me/deletion-requests', { method: 'POST', body: JSON.stringify({ scope: 'workspace_content', workspace_id: state.wsA }) });
    assert.equal(req.status, 201); assert.equal(req.body.status, 'pending'); state.requestId = req.body.request_id;
  });

  await run('inside the 7-day grace nothing is due: dry run lists nothing, --apply is refused with exit code 2, all files remain', async () => {
    const dry = purge();
    assert.equal(dry.status, 0, dry.stderr); assert.ok(!dry.stdout.includes(state.requestId), 'not due yet');
    const refused = purge('--apply', '--confirm', state.requestId);
    assert.equal(refused.status, 2); assert.match(refused.stdout, /not pending or not past the 7-day grace/);
    assert.equal(files().length, 3);
    assert.equal((await json(owner, `/v1/assets?workspace_id=${state.wsA}&kind=image`)).body.items.length, 2);
  });

  await run('after 8 days the dry run shows the plan (rows and files) and still changes nothing', async () => {
    sqliteExec(stack, 'UPDATE deletion_requests SET requested_at=? WHERE request_id=?', [new Date(Date.now() - 8 * 86400000).toISOString(), state.requestId]);
    const dry = purge();
    assert.equal(dry.status, 0, dry.stderr);
    assert.ok(dry.stdout.includes(state.requestId) && /scope=workspace_content/.test(dry.stdout) && /files=2/.test(dry.stdout) && /blocked=no/.test(dry.stdout), dry.stdout);
    assert.ok(/dry-run: nothing was changed/.test(dry.stdout));
    assert.equal(files().length, 3); assert.equal((await json(owner, `/v1/assets?workspace_id=${state.wsA}&kind=image`)).body.items.length, 2);
  });

  await run('apply: A\'s assets and files are gone, the request is no longer pending, A itself and B stay intact', async () => {
    const applied = purge('--apply', '--confirm', state.requestId);
    assert.equal(applied.status, 0, applied.stderr + applied.stdout);
    assert.match(applied.stdout, /processed rows=\d+ files=2 failed_files=0/);
    assert.equal((await json(owner, `/v1/assets?workspace_id=${state.wsA}&kind=image`)).body.items.length, 0);
    assert.equal(files().length, 1, 'only B\'s file is left');
    const mine = await json(owner, '/v1/me/deletion-requests');
    assert.notEqual(mine.body.items.find(r => r.request_id === state.requestId)?.status, 'pending');
    assert.equal((await json(owner, '/v1/workspaces')).body.items.some(w => w.workspace_id === state.wsA), true, 'the workspace itself and its members stay');
    const b = (await json(editor, `/v1/assets?workspace_id=${state.wsB}&kind=image`)).body.items;
    assert.equal(b.length, 1); assert.equal(b[0].asset_id, state.b1);
    const preview = await json(editor, `/v1/assets/${state.b1}/preview-url`, { method: 'POST' });
    assert.equal(preview.status, 200, 'B\'s image is still servable');
  });

  await run('running it again does nothing more (no pending request left)', async () => {
    const again = purge('--apply', '--confirm', state.requestId);
    assert.equal(again.status, 2); assert.equal(files().length, 1);
  });

  console.log(`SUMMARY ${results.filter(r => r.ok).length}/${results.length} purge steps passed`);
} catch { failed = true; }
finally { await stack.stop(); }
process.exit(failed ? 1 : 0);
