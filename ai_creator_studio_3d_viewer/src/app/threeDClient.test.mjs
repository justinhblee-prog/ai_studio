import test from 'node:test';
import assert from 'node:assert/strict';
import { BACKGROUNDS, validateModelFile, currentVersionId, modelContentUrl, uploadModel, MAX_MODEL_BYTES } from './threeDClient.mjs';

test('only non-empty .glb/.gltf files up to the size limit are accepted, with Korean reasons', () => {
  assert.equal(validateModelFile({ name: 'Chair.GLB', size: 10 }), '');
  assert.equal(validateModelFile({ name: 'a.gltf', size: MAX_MODEL_BYTES }), '');
  assert.match(validateModelFile({ name: 'a.obj', size: 10 }), /\.glb 또는 \.gltf/);
  assert.match(validateModelFile({ name: 'a.glb', size: MAX_MODEL_BYTES + 1 }), /너무 큽니다/);
  assert.match(validateModelFile({ name: 'a.glb', size: 0 }), /빈 파일/);
  assert.match(validateModelFile(null), /골라/);
});

test('the viewer address is the authenticated immutable version content, built from the current version', () => {
  assert.equal(currentVersionId({ items: [{ version_id: 'v1' }, { version_id: 'v2', is_current: true }] }), 'v2');
  assert.equal(currentVersionId({ items: [] }), null); assert.equal(currentVersionId(null), null);
  assert.equal(modelContentUrl('https://api.example.org/', 'a/1', 'v 2'), 'https://api.example.org/v1/assets/a%2F1/versions/v%202/preview-content');
});

test('backgrounds are valid hex colours with Korean names', () => {
  assert.ok(BACKGROUNDS.length >= 3 && BACKGROUNDS.every((b) => /^#[0-9a-f]{6}$/i.test(b.value) && /[가-힣]/.test(b.label)));
  assert.equal(new Set(BACKGROUNDS.map((b) => b.value)).size, BACKGROUNDS.length);
});

test('uploading posts the workspace and the file with the token; a refusal carries its status', async () => {
  let seen;
  globalThis.fetch = async (url, init) => { seen = { url: String(url), auth: init.headers.Authorization, ws: init.body.get('workspace_id'), name: init.body.get('file').name }; return new Response('{"asset_id":"a"}', { status: 201 }); };
  await uploadModel('http://127.0.0.1:9', 't', 'ws-1', new File([new Uint8Array(4)], 'x.glb'));
  assert.deepEqual(seen, { url: 'http://127.0.0.1:9/v1/assets', auth: 'Bearer t', ws: 'ws-1', name: 'x.glb' });
  globalThis.fetch = async () => new Response('{"detail":{"code":"ASSET_PARSE_FAILED","message":"bad"}}', { status: 422 });
  await assert.rejects(() => uploadModel('http://127.0.0.1:9', 't', 'ws-1', new File([new Uint8Array(4)], 'x.glb')), (e) => e.status === 422);
});
