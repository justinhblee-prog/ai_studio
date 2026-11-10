import assert from 'node:assert/strict';
import test from 'node:test';
import { GENERATION_LIMIT_MESSAGES, generationLimitMessage } from './generationLimits.mjs';
import { apiRequest } from './apiClient.mjs';

const CODES = ['AI_JOBS_DISABLED', 'DAILY_JOB_LIMIT_EXCEEDED', 'WORKSPACE_MONTHLY_LIMIT', 'GLOBAL_MONTHLY_LIMIT'];

test('every backend cap code maps to a Korean message without internal numbers', () => {
  for (const code of CODES) {
    const text = generationLimitMessage(code);
    assert.ok(text && /[가-힣]/.test(text), code);
    assert.ok(!/\d/.test(text), `${code} must not expose numbers`);
  }
  assert.deepEqual(Object.keys(GENERATION_LIMIT_MESSAGES).sort(), [...CODES].sort());
});

test('unknown codes and prototype keys are not mapped', () => {
  assert.equal(generationLimitMessage('SOMETHING_ELSE'), null);
  assert.equal(generationLimitMessage('toString'), null);
  assert.equal(generationLimitMessage(undefined), null);
});

test('apiRequest shows the Korean message for a 429 cap response and hides limit/used', async () => {
  const original = globalThis.fetch;
  try {
    for (const code of CODES) {
      globalThis.fetch = async () => new Response(JSON.stringify({ detail: { code, message: 'English internal', limit: 3, used: 3 } }), { status: 429 });
      await assert.rejects(() => apiRequest('http://localhost:8000', '/v1/generation-jobs', { method: 'POST', body: {} }), (error) => {
        assert.equal(error.message, GENERATION_LIMIT_MESSAGES[code]);
        assert.equal(error.code, code);
        return true;
      });
    }
    globalThis.fetch = async () => new Response(JSON.stringify({ detail: { code: 'OTHER', message: 'plain' } }), { status: 429 });
    await assert.rejects(() => apiRequest('http://localhost:8000', '/x'), /plain/);
  } finally { globalThis.fetch = original; }
});
