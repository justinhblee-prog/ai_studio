import test from 'node:test';
import assert from 'node:assert/strict';
import { isApiUrl, wrapFetch, installUnauthorizedWatcher } from './sessionGuard.mjs';

const API = 'https://api.example.org';
const respond = (status) => async () => new Response('{}', { status });

test('only addresses under the API base count as "our API"', () => {
  assert.equal(isApiUrl(`${API}/v1/assets`, `${API}/`), true);
  assert.equal(isApiUrl(API, API), true);
  for (const other of ['https://api.example.org.evil.example/v1/x', 'https://supabase.example/auth/v1/user', '/v1/assets', undefined]) assert.equal(isApiUrl(other, API), false, String(other));
  assert.equal(isApiUrl(`${API}/v1/x`, ''), false);
});

test('a 401 from the API is reported once per response and the response is passed on unchanged', async () => {
  let calls = 0;
  const guarded = wrapFetch(respond(401), { getApiBase: () => API, onUnauthorized: () => { calls += 1; } });
  const r = await guarded(`${API}/v1/assets?workspace_id=w`, { headers: { Authorization: 'Bearer t' } });
  assert.equal(r.status, 401); assert.equal(calls, 1);
  await guarded(new Request(`${API}/v1/projects`)); assert.equal(calls, 2);
});

test('other statuses, other hosts and /health never trigger it', async () => {
  let calls = 0; const onUnauthorized = () => { calls += 1; };
  for (const status of [200, 403, 404, 429, 500, 503]) await wrapFetch(respond(status), { getApiBase: () => API, onUnauthorized })(`${API}/v1/x`);
  await wrapFetch(respond(401), { getApiBase: () => API, onUnauthorized })('https://supabase.example/auth/v1/user');
  await wrapFetch(respond(401), { getApiBase: () => API, onUnauthorized })(`${API}/health`);
  assert.equal(calls, 0);
});

test('a failing callback or a failing request does not change what the caller gets', async () => {
  const boom = wrapFetch(respond(401), { getApiBase: () => API, onUnauthorized: () => { throw new Error('x'); } });
  assert.equal((await boom(`${API}/v1/x`)).status, 401);
  const down = wrapFetch(async () => { throw new TypeError('Failed to fetch'); }, { getApiBase: () => API, onUnauthorized: () => assert.fail('no response, no report') });
  await assert.rejects(() => down(`${API}/v1/x`), /Failed to fetch/);
});

test('install replaces fetch and uninstall puts the original back', async () => {
  const target = { fetch: respond(401) }; const original = target.fetch; let calls = 0;
  const off = installUnauthorizedWatcher({ getApiBase: () => API, onUnauthorized: () => { calls += 1; }, target });
  assert.notEqual(target.fetch, original);
  await target.fetch(`${API}/v1/x`); assert.equal(calls, 1);
  off(); assert.equal(target.fetch, original);
  assert.equal(typeof installUnauthorizedWatcher({ getApiBase: () => API, onUnauthorized() {}, target: {} }), 'function');
});
