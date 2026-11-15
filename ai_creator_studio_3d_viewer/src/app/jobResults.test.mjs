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

import { createJobPoller, nextPollDelay, POLL_BASE_MS, POLL_MAX_MS, IMAGE_BROKEN_MESSAGE } from './jobResults.mjs';

function fakeClock() {
  let now = 0; let next = 1; const timers = new Map();
  return {
    setTimer: (fn, ms) => { const id = next++; timers.set(id, { fn, at: now + ms }); return id; },
    clearTimer: (id) => timers.delete(id),
    pending: () => timers.size,
    now: () => now,
    async advance(ms) {
      const target = now + ms;
      for (;;) {
        const due = [...timers.entries()].filter(([, t]) => t.at <= target).sort((a, b) => a[1].at - b[1].at)[0];
        if (!due) break;
        timers.delete(due[0]); now = due[1].at; await due[1].fn();
      }
      now = target;
    },
  };
}

test('poll delay: 10s, then doubles after each consecutive failure, capped', () => {
  assert.deepEqual([0, 1, 2, 3, 4, 9].map(nextPollDelay), [10000, 20000, 40000, 80000, 80000, 80000]);
  assert.equal(POLL_BASE_MS, 10000); assert.equal(POLL_MAX_MS, 80000);
});

test('the poller requests every 10s while a job is in progress and stops by itself once none is', async () => {
  const clock = fakeClock(); let calls = 0; let active = true;
  const poller = createJobPoller({ refresh: async () => { calls += 1; if (calls === 3) active = false; }, hasActive: () => active, ...clock });
  poller.start();
  await clock.advance(9999); assert.equal(calls, 0);
  await clock.advance(1); assert.equal(calls, 1);
  await clock.advance(20000); assert.equal(calls, 3);
  await clock.advance(100000); assert.equal(calls, 3, 'no more requests once nothing is in progress');
  assert.equal(poller.running, false); assert.equal(clock.pending(), 0);
});

test('when nothing is in progress the poller never requests', async () => {
  const clock = fakeClock(); let calls = 0;
  const poller = createJobPoller({ refresh: async () => { calls += 1; }, hasActive: () => false, ...clock });
  poller.start(); await clock.advance(200000);
  assert.equal(calls, 0); assert.equal(poller.running, false);
});

test('consecutive failures slow the poller down; a success resets it', async () => {
  const clock = fakeClock(); const at = []; let fail = true;
  const poller = createJobPoller({ refresh: async () => { at.push(clock.now()); if (fail) throw new Error('x'); }, hasActive: () => true, ...clock });
  poller.start();
  await clock.advance(70000);                       // fails at 10s, 30s, 70s (gaps 20s, 40s)
  assert.deepEqual(at, [10000, 30000, 70000]);
  fail = false; await clock.advance(80000);         // 4th call at 150s succeeds -> back to 10s gaps
  assert.equal(at.at(-1), 150000);
  await clock.advance(10000);
  assert.equal(at.at(-1), 160000);
  poller.stop();
});

test('a hidden tab makes no request, and stop() cancels the pending timer', async () => {
  const clock = fakeClock(); let calls = 0; let hidden = true;
  const poller = createJobPoller({ refresh: async () => { calls += 1; }, hasActive: () => true, isHidden: () => hidden, ...clock });
  poller.start(); await clock.advance(60000);
  assert.equal(calls, 0, 'hidden: nothing requested');
  hidden = false; await clock.advance(10000);
  assert.equal(calls, 1);
  poller.stop(); assert.equal(clock.pending(), 0); assert.equal(poller.running, false);
  await clock.advance(100000); assert.equal(calls, 1);
});

test('the broken-image notice is Korean', () => assert.match(IMAGE_BROKEN_MESSAGE, /표시하지 못했습니다/));
