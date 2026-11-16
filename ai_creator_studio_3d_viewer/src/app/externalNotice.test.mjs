import test from 'node:test';
import assert from 'node:assert/strict';
import { noticeFromError, acknowledgeNotice } from './externalNotice.mjs';
import { apiRequest } from './apiClient.mjs';

const API = 'http://127.0.0.1:9';
const POLICY = { trains_on_customer_content: false, input_retention: 'base64 input is deleted after processing', output_retention: 'CDN output is deleted after 3 days',
  request_log_deletion: 'ask the provider by e-mail', terms_check_required: true };

test('the 409 refusal becomes a Korean notice that names the provider, the data facts and the terms caveat', async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: { code: 'EXTERNAL_NOTICE_REQUIRED', provider: 'fashn', message: 'English', data_policy: POLICY } }), { status: 409 });
  const error = await apiRequest(API, '/v1/generation-jobs', { token: 't', method: 'POST', body: {} }).catch((e) => e);
  const notice = noticeFromError(error);
  assert.equal(notice.provider, 'fashn');
  assert.match(notice.lines[0], /외부 AI 서비스\(fashn\)로 사진이 전송됩니다/);
  assert.ok(notice.lines.some((l) => /학습에 사용하지 않는다/.test(l)));
  assert.ok(notice.lines.some((l) => l.includes('3 days')) && notice.lines.some((l) => /약관 확인이 필요/.test(l)));
});

test('unknown data handling is stated as unknown, not as safe', () => {
  const notice = noticeFromError(Object.assign(new Error('x'), { code: 'EXTERNAL_NOTICE_REQUIRED', detail: { provider: 'new-one', data_policy: { trains_on_customer_content: null, terms_check_required: true } } }));
  assert.ok(notice.lines.some((l) => /학습에 사용하는지 확인되지 않았습니다/.test(l)));
  assert.ok(!notice.lines.some((l) => /사용하지 않는다/.test(l)));
  assert.equal(noticeFromError(Object.assign(new Error('x'), { code: 'EXTERNAL_NOTICE_REQUIRED', detail: {} })).provider, '외부 AI 서비스');
});

test('any other error is not a notice', () => {
  for (const e of [new Error('x'), Object.assign(new Error('x'), { code: 'LIBRARY_IMPORT_LIMIT' }), null, undefined]) assert.equal(noticeFromError(e), null);
});

test('acknowledging posts the workspace and the provider', async () => {
  let seen;
  globalThis.fetch = async (url, init) => { seen = { url: String(url).replace(API, ''), body: JSON.parse(init.body), auth: init.headers.Authorization }; return new Response(JSON.stringify({ provider: 'fashn', acknowledged: true, acknowledged_at: 't' }), { status: 200 }); };
  await acknowledgeNotice(API, 'tok', 'ws-1', 'fashn');
  assert.deepEqual(seen, { url: '/v1/external-provider-notices', body: { workspace_id: 'ws-1', provider: 'fashn' }, auth: 'Bearer tok' });
});
