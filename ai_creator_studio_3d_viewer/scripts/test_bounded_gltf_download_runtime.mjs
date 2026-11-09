import assert from 'node:assert/strict';
import { MAX_MODEL_DOWNLOAD_BYTES, ModelDownloadError, getHttpDownloadError, readModelResponse } from '../src/boundedModelDownload.mjs';

const bytes = (...values) => new Uint8Array(values);
const response = (chunks, headers = {}, options = {}) => {
  let cancelled = false;
  let index = 0;
  const stream = new ReadableStream({
    pull(controller) {
      if (options.pending || options.keepOpen) return;
      if (index < chunks.length) controller.enqueue(chunks[index++]);
      else controller.close();
    },
    cancel() { cancelled = true; options.onCancel?.(); },
  }, { highWaterMark: 0 });
  return { value: new Response(stream, { headers }), get cancelled() { return cancelled; }, options };
};
const signal = () => new AbortController();
const checks = [];
async function check(name, fn) { await fn(); checks.push(name); }

await check('known content length assembles bytes and reports progress', async () => {
  const r = response([bytes(1, 2), bytes(3, 4)], { 'content-length': '4' });
  const progress = [];
  const result = await readModelResponse(r.value, signal().signal, (n) => progress.push(n));
  assert.deepEqual([...new Uint8Array(result)], [1, 2, 3, 4]);
  assert.equal(progress.at(-1), 95);
});
await check('unknown content length is supported', async () => {
  const r = response([bytes(5, 6)]);
  assert.deepEqual([...new Uint8Array(await readModelResponse(r.value, signal().signal))], [5, 6]);
});
await check('known content length writes directly into one exact-size result buffer', async () => {
  const r = response([bytes(1, 2), bytes(3, 4)], { 'content-length': '4' });
  const result = await readModelResponse(r.value, signal().signal);
  assert.equal(result.byteLength, 4);
  assert.deepEqual([...new Uint8Array(result)], [1, 2, 3, 4]);
});
await check('zero-length known response returns an empty buffer', async () => {
  const r = response([], { 'content-length': '0' });
  assert.equal((await readModelResponse(r.value, signal().signal)).byteLength, 0);
});
await check('unknown-length stream grows a capped buffer and preserves all bytes', async () => {
  const first = new Uint8Array(70 * 1024).fill(7);
  const second = new Uint8Array(90 * 1024).fill(9);
  const r = response([first, second]);
  const result = new Uint8Array(await readModelResponse(r.value, signal().signal));
  assert.equal(result.byteLength, 160 * 1024);
  assert.equal(result[0], 7);
  assert.equal(result[70 * 1024], 9);
  assert.equal(result.at(-1), 9);
});
await check('unknown-length empty stream returns a zero-byte buffer', async () => {
  const r = response([]);
  assert.equal((await readModelResponse(r.value, signal().signal)).byteLength, 0);
});
await check('unknown-length final trim allocation failure maps to typed memory error', async () => {
  const r = response([bytes(1, 2, 3)]);
  const originalSlice = Uint8Array.prototype.slice;
  Uint8Array.prototype.slice = function () { throw new RangeError('simulated final trim allocation failure'); };
  try {
    await assert.rejects(
      readModelResponse(r.value, signal().signal),
      (e) => e instanceof ModelDownloadError && e.code === 'memory',
    );
  } finally {
    Uint8Array.prototype.slice = originalSlice;
  }
});
await check('unknown-length allocation failure cancels the reader with a typed memory error', async () => {
  const r = response([bytes(1, 2, 3)]);
  const OriginalUint8Array = globalThis.Uint8Array;
  globalThis.Uint8Array = function () { throw new RangeError('simulated allocation failure'); };
  try {
    await assert.rejects(readModelResponse(r.value, signal().signal), (e) => e instanceof ModelDownloadError && e.code === 'memory');
  } finally {
    globalThis.Uint8Array = OriginalUint8Array;
  }
  assert.equal(r.cancelled, true);
});
await check('known-length allocation failure cancels the unlocked response body', async () => {
  const r = response([bytes(1, 2, 3)], { 'content-length': '3' });
  const OriginalUint8Array = globalThis.Uint8Array;
  globalThis.Uint8Array = function () { throw new RangeError('simulated allocation failure'); };
  try {
    await assert.rejects(readModelResponse(r.value, signal().signal), (e) => e instanceof ModelDownloadError && e.code === 'memory');
  } finally {
    globalThis.Uint8Array = OriginalUint8Array;
  }
  assert.equal(r.cancelled, true);
});
await check('declared size above cap rejected and response body cancelled before read', async () => {
  const r = response([bytes(1)] , { 'content-length': String(MAX_MODEL_DOWNLOAD_BYTES + 1) });
  await assert.rejects(readModelResponse(r.value, signal().signal), (e) => e instanceof ModelDownloadError && e.code === 'too_large');
  assert.equal(r.cancelled, true);
});
await check('actual stream crossing cap is cancelled', async () => {
  const huge = new Uint8Array(MAX_MODEL_DOWNLOAD_BYTES);
  const r = response([huge, bytes(1)]);
  await assert.rejects(readModelResponse(r.value, signal().signal), (e) => e.code === 'too_large');
  assert.equal(r.cancelled, true);
});
await check('abort before reading rejects', async () => {
  const c = new AbortController(); c.abort();
  const r = response([bytes(1)]);
  await assert.rejects(readModelResponse(r.value, c.signal), (e) => e.name === 'AbortError');
});
await check('abort during pending read cancels stream', async () => {
  const c = new AbortController();
  let cancelCalled = false;
  const stream = new ReadableStream({ pull() {}, cancel() { cancelCalled = true; } });
  const pending = readModelResponse(new Response(stream), c.signal);
  await new Promise((resolve) => setTimeout(resolve, 0));
  c.abort();
  await assert.rejects(pending, (e) => e.name === 'AbortError');
  assert.equal(cancelCalled, true);
});
await check('truncated declared transfer maps to network error', async () => {
  const r = response([bytes(1, 2)], { 'content-length': '3' });
  await assert.rejects(readModelResponse(r.value, signal().signal), (e) => e.code === 'network');
});
await check('stream exceeding declared length is cancelled and rejected', async () => {
  const r = response([bytes(1, 2, 3)], { 'content-length': '2' });
  await assert.rejects(readModelResponse(r.value, signal().signal), (e) => e.code === 'network');
  assert.equal(r.cancelled, true);
});
await check('HTTP access and version statuses map to safe typed errors', async () => {
  for (const [status, code] of [[401,'unauthorized'],[403,'forbidden'],[404,'not_found'],[409,'conflict']]) {
    const error = getHttpDownloadError(status); assert.equal(error.status, status); assert.equal(error.code, code);
  }
});
await check('malformed, negative, decimal, and empty lengths are rejected', async () => {
  for (const value of ['invalid', '-1', '1.5', '']) {
    const r = response([bytes(9)], { 'content-length': value });
    await assert.rejects(readModelResponse(r.value, signal().signal), (e) => e.code === 'network');
    assert.equal(r.cancelled, true);
  }
});
console.log(`Bounded GLTF download runtime: ${checks.length}/${checks.length} passed`);
for (const name of checks) console.log(`PASS ${name}`);
