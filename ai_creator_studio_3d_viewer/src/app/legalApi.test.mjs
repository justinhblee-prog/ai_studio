import test from 'node:test';
import assert from 'node:assert/strict';
import { acceptRequired, gateState, loadConsents, setConsent, requestAccountDeletion, cancelDeletionRequest, loadDeletionRequests } from './legalApi.mjs';

const API = 'http://127.0.0.1:9';
function fakeFetch(handler) {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    const call = { url: String(url).replace(API, ''), method: init.method, body: init.body ? JSON.parse(init.body) : undefined, auth: init.headers.Authorization };
    calls.push(call);
    const { status = 200, body = {} } = handler(call);
    return new Response(status === 204 ? null : JSON.stringify(body), { status });
  };
  return calls;
}

test('acceptance sends exactly the versions the server lists as missing, with the user token', async () => {
  const status = { accepted: false, required: [{ document: 'terms', version: 'v2' }, { document: 'privacy', version: 'v2' }], missing: [{ document: 'privacy', version: 'v2' }], history: [] };
  const calls = fakeFetch(() => ({ body: { accepted: true } }));
  await acceptRequired(API, 'tok', status);
  assert.deepEqual(calls, [{ url: '/v1/me/legal-acceptances', method: 'POST', body: { documents: [{ document: 'privacy', version: 'v2' }] }, auth: 'Bearer tok' }]);
});

test('nothing is sent when nothing is missing and nothing is required', async () => {
  const calls = fakeFetch(() => ({}));
  await acceptRequired(API, 'tok', { accepted: true, required: [], missing: [], history: [] });
  assert.equal(calls.length, 0);
});

test('the gate opens only on an explicit accepted=true; a failed check is an error, never open', () => {
  assert.equal(gateState({ accepted: true }, null), 'open');
  assert.equal(gateState({ accepted: false }, null), 'needs-acceptance');
  assert.equal(gateState(null, null), 'loading');
  assert.equal(gateState({ accepted: true }, new Error('network')), 'error');
  assert.equal(gateState(undefined, new Error('network')), 'error');
});

test('the AI-training consent is its own call and always an explicit boolean', async () => {
  const calls = fakeFetch(() => ({ body: { items: [{ purpose: 'ai_training', granted: false }] } }));
  assert.deepEqual(await setConsent(API, 'tok', 'ai_training', 0), [{ purpose: 'ai_training', granted: false }]);
  assert.deepEqual(calls[0], { url: '/v1/me/consents/ai_training', method: 'PUT', body: { granted: false }, auth: 'Bearer tok' });
  assert.deepEqual(await loadConsents(API, 'tok'), [{ purpose: 'ai_training', granted: false }]);
});

test('deletion requests: account scope, optional trimmed reason, list and cancel by id', async () => {
  const calls = fakeFetch(c => c.method === 'DELETE' ? { status: 204 } : c.method === 'GET' ? { body: { items: [{ request_id: 'del_1', status: 'pending' }] } } : { status: 201, body: { request_id: 'del_1' } });
  await requestAccountDeletion(API, 'tok', '  no longer needed ');
  await requestAccountDeletion(API, 'tok', '   ');
  assert.deepEqual(calls.map(c => c.body), [{ scope: 'account', reason: 'no longer needed' }, { scope: 'account' }]);
  assert.deepEqual(await loadDeletionRequests(API, 'tok'), [{ request_id: 'del_1', status: 'pending' }]);
  await cancelDeletionRequest(API, 'tok', 'del/1');
  assert.equal(calls.at(-1).url, '/v1/me/deletion-requests/del%2F1');
});
