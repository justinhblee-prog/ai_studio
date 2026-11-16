// R-038 in the browser: 3D Studio (viewing). Real: web bundle, backend (FEATURE_THREE_D=1), SQLite. Mocked: Supabase Auth.
// NOT covered: the WebGL picture itself (headless CI has no reliable GPU); the screen's wiring, upload, selection and rules are.
import assert from 'node:assert/strict';
import { startStack, chromium, mockSupabase, loginThroughUi, gotoPage, makeRunner, apiCall, USERS } from './harness.mjs';

function glb() {   // the smallest valid glTF 2.0 binary container (JSON chunk only), as the backend's own tests build it
  let doc = Buffer.from(JSON.stringify({ asset: { version: '2.0' } }));
  doc = Buffer.concat([doc, Buffer.alloc((4 - (doc.length % 4)) % 4, 0x20)]);
  const chunk = Buffer.alloc(8); chunk.writeUInt32LE(doc.length, 0); chunk.writeUInt32LE(0x4E4F534A, 4);
  const header = Buffer.alloc(12); header.write('glTF', 0, 'ascii'); header.writeUInt32LE(2, 4); header.writeUInt32LE(12 + 8 + doc.length, 8);
  return Buffer.concat([header, chunk, doc]);
}

const stack = await startStack({ extraEnv: { FEATURE_THREE_D: '1' } });
const browser = await chromium.launch();
let failed = false;
try {
  const context = await browser.newContext(); await mockSupabase(context, USERS.owner);
  const page = await context.newPage();
  const { run, results } = makeRunner(page, stack);
  const state = {};
  const screen = () => page.locator('section[aria-label="3D 스튜디오"]');
  const stage = () => screen().getByTestId('three-d-stage');
  const models = async () => (await apiCall(stack, USERS.owner.token, `/v1/assets?workspace_id=${state.workspace}&kind=model`)).body.items;

  await run('the screen opens without models, with the service on and a stage', async () => {
    await loginThroughUi(page, stack.webUrl, USERS.owner);
    state.workspace = await page.locator('.workspace-select').inputValue();
    await gotoPage(page, '3D 스튜디오');
    await screen().getByRole('option', { name: '올린 모델이 없습니다' }).waitFor({ state: 'attached', timeout: 10000 });
    assert.equal(await screen().getByText('파일럿 시험판').count(), 0);
    assert.equal(await stage().getAttribute('data-model'), '');
  });

  await run('uploading a .glb stores it as a model asset, lists it and selects it for the stage', async () => {
    await screen().getByLabel('3D 모델 올리기').setInputFiles({ name: 'chair.glb', mimeType: 'model/gltf-binary', buffer: glb() });
    await page.waitForFunction(() => !!document.querySelector('[data-testid="three-d-stage"]')?.getAttribute('data-model'), null, { timeout: 15000 });
    const stored = await models();
    assert.equal(stored.length, 1); assert.equal(stored[0].original_filename, 'chair.glb');
    assert.equal(await stage().getAttribute('data-model'), stored[0].asset_id);
    assert.equal(await screen().getByLabel('내 3D 모델').inputValue(), stored[0].asset_id);
    state.assetId = stored[0].asset_id;
  });

  await run('the model is only reachable through the authenticated version content, not through an open address', async () => {
    const versions = (await apiCall(stack, USERS.owner.token, `/v1/assets/${state.assetId}/versions`)).body.items;
    const versionId = versions.find(v => v.is_current).version_id;
    const url = `${stack.apiUrl}/v1/assets/${state.assetId}/versions/${versionId}/preview-content`;
    assert.equal((await fetch(url)).status, 401, 'no token, no model');
    const ok = await fetch(url, { headers: { Authorization: `Bearer ${USERS.owner.token}` } });
    assert.equal(ok.status, 200); assert.deepEqual(Buffer.from(await ok.arrayBuffer()), glb());
    assert.equal((await fetch(url, { headers: { Authorization: `Bearer ${USERS.editor.token}` } })).status, 404, 'another workspace member-less user cannot see it');
  });

  await run('the stage background can be changed', async () => {
    await screen().getByLabel('무대 배경').selectOption({ label: '밝은 회색' });
    assert.equal(await stage().getAttribute('data-background'), '#e8eaed');
  });

  await run('a file that is not a 3D model is refused in Korean and nothing is stored', async () => {
    await screen().getByLabel('3D 모델 올리기').setInputFiles({ name: 'notes.txt', mimeType: 'text/plain', buffer: Buffer.from('hello') });
    await screen().getByText(/\.glb 또는 \.gltf 파일만/).waitFor({ timeout: 10000 });
    assert.equal((await models()).length, 1);
    await screen().getByLabel('3D 모델 올리기').setInputFiles({ name: 'broken.glb', mimeType: 'model/gltf-binary', buffer: Buffer.from('this is not a glb at all') });
    await screen().locator('[role=alert]').filter({ hasText: /./ }).first().waitFor({ timeout: 10000 });
    assert.equal((await models()).length, 1, 'the server validated the container and stored nothing');
  });

  await run('with the service switched off the screen says so, refuses uploads and still lists existing models', async () => {
    await page.route(/\/v1\/features$/, route => route.fulfill({ status: 200, contentType: 'application/json', headers: { 'access-control-allow-origin': '*' },
      body: JSON.stringify({ features: { three_d: { enabled: false, status: 'pilot_preview' } } }) }));
    await page.reload(); await page.locator('.workspace-select').waitFor({ timeout: 20000 });
    await gotoPage(page, '3D 스튜디오');
    await screen().getByText('파일럿 시험판').waitFor({ timeout: 10000 });
    assert.equal(await screen().getByLabel('3D 모델 올리기').isDisabled(), true);
    assert.ok(await screen().getByLabel('내 3D 모델').locator('option', { hasText: 'chair.glb' }).count() === 1);
  });

  console.log(`SUMMARY ${results.filter(r => r.ok).length}/${results.length} three-d steps passed`);
} catch { failed = true; }
finally { await browser.close(); await stack.stop(); }
process.exit(failed ? 1 : 0);
