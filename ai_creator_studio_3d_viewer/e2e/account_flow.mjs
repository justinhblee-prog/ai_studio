// Account and data-protection API flows against the real backend over HTTP (SQLite, mock provider): legal acceptance,
// deletion requests, and the Character reference guard on asset deletion. API level only: none of these has a screen yet,
// so no browser page is driven. Supabase is not involved (bearer tokens are checked by the backend itself).
import assert from 'node:assert/strict';
import { startStack, makeRunner, apiCall, makePng, USERS } from './harness.mjs';

const stack = await startStack({ apiPort: 8766, webPort: 4766 });
let failed = false;
const json = (token, path, init = {}) => apiCall(stack, token, path, { ...init, headers: { 'Content-Type': 'application/json', ...(init.headers || {}) } });
try {
  const { run, results } = makeRunner({ locator: () => ({ innerText: async () => '' }) }, stack);
  const owner = USERS.owner.token, editor = USERS.editor.token, outsider = USERS.outsider.token;
  const ws = 'ws_acct' + Math.random().toString(16).slice(2, 8);

  await run('legal documents are public; a new user must accept the current versions, and a stale version is refused', async () => {
    const pub = await fetch(stack.apiUrl + '/v1/legal/documents');
    assert.equal(pub.status, 200);
    const docs = (await pub.json()).documents;
    assert.deepEqual(docs.map(d => d.document).sort(), ['content_policy', 'privacy', 'terms']);
    const before = await json(owner, '/v1/me/legal-status');
    assert.equal(before.body.accepted, false); assert.equal(before.body.missing.length, 3);
    const stale = await json(owner, '/v1/me/legal-acceptances', { method: 'POST', body: JSON.stringify({ documents: [{ document: 'terms', version: 'old-version' }] }) });
    assert.equal(stale.status, 409);
    const ok = await json(owner, '/v1/me/legal-acceptances', { method: 'POST', body: JSON.stringify({ documents: docs }) });
    assert.equal(ok.status, 200); assert.equal(ok.body.accepted, true);
    assert.equal((await json(outsider, '/v1/me/legal-status')).body.accepted, false, 'another user is unaffected');
  });

  await run('deletion request: create, replay returns the same request, list, cancel once, cancel again is refused', async () => {
    const first = await json(owner, '/v1/me/deletion-requests', { method: 'POST', body: JSON.stringify({ scope: 'account' }) });
    assert.equal(first.status, 201); assert.equal(first.body.status, 'pending');
    const again = await json(owner, '/v1/me/deletion-requests', { method: 'POST', body: JSON.stringify({ scope: 'account' }) });
    assert.equal(again.status, 200); assert.equal(again.body.request_id, first.body.request_id);
    const list = await json(owner, '/v1/me/deletion-requests');
    assert.equal(list.body.items.length, 1);
    const cancel = await fetch(stack.apiUrl + `/v1/me/deletion-requests/${first.body.request_id}`, { method: 'DELETE', headers: { Authorization: `Bearer ${owner}` } });
    assert.equal(cancel.status, 204);
    const twice = await fetch(stack.apiUrl + `/v1/me/deletion-requests/${first.body.request_id}`, { method: 'DELETE', headers: { Authorization: `Bearer ${owner}` } });
    assert.equal(twice.status, 409);
    assert.equal((await json(owner, '/v1/me/deletion-requests')).body.items[0].status, 'cancelled');
  });

  await run('deletion requests are private to their owner, and workspace content deletion needs the owner role', async () => {
    const mine = await json(owner, '/v1/me/deletion-requests', { method: 'POST', body: JSON.stringify({ scope: 'account', reason: 'again' }) });
    assert.equal(mine.status, 201);
    assert.equal((await json(outsider, '/v1/me/deletion-requests')).body.items.length, 0, 'an outsider sees none');
    const steal = await fetch(stack.apiUrl + `/v1/me/deletion-requests/${mine.body.request_id}`, { method: 'DELETE', headers: { Authorization: `Bearer ${outsider}` } });
    assert.equal(steal.status, 404, 'an outsider cannot cancel it');
    assert.equal((await json(owner, '/v1/workspaces', { method: 'POST', body: JSON.stringify({ workspace_id: ws }) })).status, 201);
    assert.equal((await json(owner, `/v1/workspaces/${ws}/members`, { method: 'POST', body: JSON.stringify({ user_id: USERS.editor.id, role: 'editor' }) })).status, 201);
    const asEditor = await json(editor, '/v1/me/deletion-requests', { method: 'POST', body: JSON.stringify({ scope: 'workspace_content', workspace_id: ws }) });
    assert.equal(asEditor.status, 403);
    const asOwner = await json(owner, '/v1/me/deletion-requests', { method: 'POST', body: JSON.stringify({ scope: 'workspace_content', workspace_id: ws }) });
    assert.equal(asOwner.status, 201);
  });

  await run('an asset used by a Character cannot be deleted until the Character is removed', async () => {
    const form = new FormData(); form.set('workspace_id', ws); form.set('rights_confirmed', 'true'); form.set('depicts_person', 'false'); form.set('likeness_consent', 'false');
    form.set('file', new Blob([makePng(32, 24, [20, 80, 140])], { type: 'image/png' }), 'ref.png');
    const up = await fetch(stack.apiUrl + '/v1/assets/images', { method: 'POST', headers: { Authorization: `Bearer ${owner}` }, body: form });
    assert.equal(up.status, 201); const assetId = (await up.json()).asset_id;
    const body = { identity: { name: 'Mina', gender: 'female', face_shape: 'oval', hairstyle: 'long', body_type: 'athletic', skin_tone: 'medium' },
      outfits: [{ id: 'o1', name: 'Casual', category: 'casual', top: 'shirt' }], active_outfit_id: 'o1', asset_ids: [assetId] };
    const char = await json(owner, `/v1/workspaces/${ws}/characters`, { method: 'POST', body: JSON.stringify(body) });
    assert.equal(char.status, 201, JSON.stringify(char.body));
    const del = () => fetch(stack.apiUrl + `/v1/assets/${assetId}`, { method: 'DELETE', headers: { Authorization: `Bearer ${owner}` } });
    const blocked = await del(); assert.equal(blocked.status, 409); assert.match(await blocked.text(), /Character/);
    const rm = await fetch(stack.apiUrl + `/v1/workspaces/${ws}/characters/${char.body.character_id}`, { method: 'DELETE', headers: { Authorization: `Bearer ${owner}` } });
    assert.equal(rm.status, 204);
    assert.equal((await del()).status, 204);
  });

  console.log(`SUMMARY ${results.filter(r => r.ok).length}/${results.length} account flow steps passed`);
} catch (error) { if (!(globalThis.__reported)) console.log('ERROR ' + (error && error.stack || error).toString().slice(0, 800)); failed = true; }
finally { await stack.stop(); }
process.exit(failed ? 1 : 0);
