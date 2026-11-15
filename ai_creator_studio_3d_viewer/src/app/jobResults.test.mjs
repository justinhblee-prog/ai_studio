import test from 'node:test';
import assert from 'node:assert/strict';
import { statusGroup, statusLabel, isActive, failureMessage, listGenerationJobs, loadJobResultBlob, EMPTY_LIST_MESSAGE, NO_RESULT_MESSAGE } from './jobResults.mjs';

const API = 'http://127.0.0.1:9';
function fakeFetch(handler) {
  const calls = [];
  globalThis.fetch = async (url, init = {}) => {
    const call = { url: String(url).replace(API, ''), headers: init.headers };
    calls.push(call);
    const { status = 200, body = {}, raw } = handler(call);
    return new Response(raw ?? JSON.stringify(body), { status });
  };
  return calls;
}

test('the 5 server statuses show as exactly 4 Korean states', () => {
  assert.deepEqual(['queued', 'running', 'post_processing', 'succeeded', 'failed'].map(statusLabel), ['대기', '진행', '진행', '완료', '실패']);
  assert.equal(new Set(['queued', 'running', 'succeeded', 'failed'].map(statusLabel)).size, 4);
  assert.equal(statusLabel('weird'), '알 수 없음');
  assert.equal(isActive('queued'), true); assert.equal(isActive('post_processing'), true);
  assert.equal(isActive('succeeded'), false); assert.equal(isActive('failed'), false);
});

test('a failed job gets Korean guidance, never the raw English code or a blank', () => {
  for (const code of ['PROVIDER_GENERATION_FAILED', 'PROVIDER_OUTPUT_MISSING', 'PROVIDER_START_UNKNOWN', 'OUTPUT_SAVE_PENDING', 'JOB_CANCELLED', 'SOMETHING_NEW', null, undefined]) {
    const text = failureMessage(code);
    assert.match(text, /[가-힣]/, String(code));
    assert.ok(!text.includes('PROVIDER_') && !text.includes('_'), String(code));
  }
  assert.notEqual(failureMessage('JOB_CANCELLED'), failureMessage('PROVIDER_GENERATION_FAILED'));
});

test('the list is read from the existing workspace-scoped endpoint with the token', async () => {
  const calls = fakeFetch(() => ({ body: [{ job_id: 'j2', status: 'queued', provider: 'mock' }] }));
  const jobs = await listGenerationJobs(API, 'tok', 'ws 1');
  assert.equal(jobs.length, 1);
  assert.equal(calls[0].url, '/v1/generation-jobs?workspace_id=ws%201&limit=50&offset=0');
  assert.equal(calls[0].headers.Authorization, 'Bearer tok');
  assert.match(EMPTY_LIST_MESSAGE, /아직 생성 작업이 없습니다/);
});

test('result image: only a succeeded job with an output is fetched; 404 or no output means the empty state, not an error', async () => {
  const calls = fakeFetch(() => ({ raw: 'PNGDATA' }));
  for (const job of [{ job_id: 'a', status: 'queued', output_url: '/x' }, { job_id: 'b', status: 'failed', output_url: '/x' }, { job_id: 'c', status: 'succeeded', output_url: null }]) {
    assert.equal(await loadJobResultBlob(API, 'tok', job), null);
  }
  assert.equal(calls.length, 0, 'no request for jobs that cannot have an image');
  const blob = await loadJobResultBlob(API, 'tok', { job_id: 'd/1', status: 'succeeded', output_url: '/v1/generation-jobs/d/output' });
  assert.equal(await blob.text(), 'PNGDATA');
  assert.equal(calls[0].url, '/v1/generation-jobs/d%2F1/output');
  assert.equal(calls[0].headers.Authorization, 'Bearer tok');
  fakeFetch(() => ({ status: 404 }));
  assert.equal(await loadJobResultBlob(API, 'tok', { job_id: 'e', status: 'succeeded', output_url: '/x' }), null);
  fakeFetch(() => ({ status: 500 }));
  await assert.rejects(() => loadJobResultBlob(API, 'tok', { job_id: 'f', status: 'succeeded', output_url: '/x' }), /결과 이미지를 불러오지 못했습니다/);
  assert.match(NO_RESULT_MESSAGE, /시험/);
});
