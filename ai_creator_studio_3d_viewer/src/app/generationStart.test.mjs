import test from 'node:test';
import assert from 'node:assert/strict';
import { resolvePublicBase, generationReady, absolutizePreviewUrl, buildGenerationRequest, startGeneration, NOT_READY_MESSAGE } from './generationStart.mjs';
import { GENERATION_LIMIT_MESSAGES } from './generationLimits.mjs';

const API = 'http://127.0.0.1:9';
const PUBLIC = 'https://api.example.org';

function fakeFetch(handler) {
  const calls = [];
  globalThis.fetch = async (url, init = {}) => {
    const call = { url: String(url).replace(API, ''), method: init.method || 'GET', body: init.body ? JSON.parse(init.body) : undefined, headers: init.headers };
    calls.push(call);
    const { status = 200, body = {} } = handler(call);
    return new Response(JSON.stringify(body), { status });
  };
  return calls;
}
const happy = (call) => {
  if (call.url.endsWith('/versions')) return { body: { items: [{ version_id: 'v-old', is_current: false }, { version_id: `v-${call.url.split('/')[3]}`, is_current: true }] } };
  if (call.url.endsWith('/preview-url')) return { body: { url: `/v1/assets/${call.url.split('/')[3]}/versions/x/preview?expires=1&signature=s` } };
  return { status: 202, body: { job_id: 'job_1', status: 'queued', provider: 'mock' } };
};
const args = (over = {}) => ({ api: API, token: 'tok', publicBase: PUBLIC, workspaceId: 'ws-1', modelAssetId: 'asset-m', garmentAssetId: 'asset-g', ...over });

test('an empty, http, malformed or query-carrying public address means "not ready"', () => {
  for (const bad of ['', '   ', undefined, 'http://api.example.org', 'api.example.org', 'https://x.org/?a=1', 'ftp://x.org']) assert.equal(generationReady(bad), false, String(bad));
  assert.equal(resolvePublicBase(' https://api.example.org/// '), 'https://api.example.org');
  assert.equal(generationReady(PUBLIC), true);
});

test('when the address is empty the request is blocked before ANY network call', async () => {
  const calls = fakeFetch(happy);
  await assert.rejects(() => startGeneration(args({ publicBase: '' })), (error) => error.message === NOT_READY_MESSAGE);
  assert.equal(calls.length, 0);
});

test('both images are required before anything is sent', async () => {
  const calls = fakeFetch(happy);
  await assert.rejects(() => startGeneration(args({ garmentAssetId: '' })), /모두 선택/);
  assert.equal(calls.length, 0);
});

test('the signed relative path gets the public address; other paths are refused', () => {
  assert.equal(absolutizePreviewUrl(PUBLIC, '/v1/assets/a1/versions/v1/preview?expires=1&signature=s'), `${PUBLIC}/v1/assets/a1/versions/v1/preview?expires=1&signature=s`);
  for (const bad of ['https://evil.example/x', '/v1/other/a1/preview?x=1', '/v1/assets/a1/preview', undefined]) assert.throws(() => absolutizePreviewUrl(PUBLIC, bad), /이미지 주소/);
  assert.throws(() => absolutizePreviewUrl('', '/v1/assets/a/preview?x=1'), (error) => error.message === NOT_READY_MESSAGE);
});

test('the job request uses the current version of each asset and carries the chosen options and an idempotency key', async () => {
  const calls = fakeFetch(happy);
  const job = await startGeneration(args({ options: { category: 'tops', mode: 'quality', resolution: '4k', outputFormat: 'jpeg', prompt: '  밝게  ' }, idempotencyKey: 'gen-key-1' }));
  assert.equal(job.job_id, 'job_1');
  const urls = calls.filter((c) => c.url.endsWith('/preview-url'));
  assert.deepEqual(urls.map((c) => c.url), ['/v1/assets/asset-m/versions/v-asset-m/preview-url', '/v1/assets/asset-g/versions/v-asset-g/preview-url']);
  assert.ok(urls.every((c) => c.method === 'POST'));
  const post = calls.at(-1);
  assert.equal(post.url, '/v1/generation-jobs');
  assert.equal(post.headers['Idempotency-Key'], 'gen-key-1');
  assert.equal(post.headers.Authorization, 'Bearer tok');
  assert.deepEqual(post.body, {
    workspace_id: 'ws-1', model_image_url: `${PUBLIC}/v1/assets/asset-m/versions/x/preview?expires=1&signature=s`,
    garment_image_url: `${PUBLIC}/v1/assets/asset-g/versions/x/preview?expires=1&signature=s`,
    category: 'tops', mode: 'quality', resolution: '4k', output_format: 'jpeg', prompt: '밝게',
  });
});

test('defaults match the server schema and an empty prompt is omitted', () => {
  assert.deepEqual(buildGenerationRequest({ workspaceId: 'w', modelUrl: 'https://a', garmentUrl: 'https://b' }),
    { workspace_id: 'w', model_image_url: 'https://a', garment_image_url: 'https://b', category: 'auto', mode: 'balanced', resolution: '2k', output_format: 'png' });
  assert.equal(buildGenerationRequest({ workspaceId: 'w', modelUrl: 'a', garmentUrl: 'b', prompt: 'x'.repeat(600) }).prompt.length, 500);
});

test('the four 429 cap responses reach the user as the Korean messages (R-016)', async () => {
  for (const code of ['AI_JOBS_DISABLED', 'DAILY_JOB_LIMIT_EXCEEDED', 'WORKSPACE_MONTHLY_LIMIT', 'GLOBAL_MONTHLY_LIMIT']) {
    fakeFetch((call) => (call.url === '/v1/generation-jobs' ? { status: 429, body: { detail: { code, message: 'English internal' } } } : happy(call)));
    await assert.rejects(() => startGeneration(args()), (error) => {
      assert.equal(error.message, GENERATION_LIMIT_MESSAGES[code]);
      return true;
    });
  }
});

test('a version without a current flag stops before the job is created', async () => {
  const calls = fakeFetch((call) => (call.url.endsWith('/versions') ? { body: { items: [{ version_id: 'v1', is_current: false }] } } : happy(call)));
  await assert.rejects(() => startGeneration(args()), /현재 버전/);
  assert.ok(!calls.some((c) => c.url === '/v1/generation-jobs'));
});
