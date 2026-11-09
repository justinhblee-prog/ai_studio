// L-04 in the browser: the image upload declares rights / likeness consent and the server (flag ON) enforces it.
// Real: web bundle, backend, SQLite. Mocked: Supabase Auth. No AI provider is called.
import assert from 'node:assert/strict';
import { startStack, chromium, mockSupabase, loginThroughUi, gotoPage, makePng, makeRunner, apiCall, USERS } from './harness.mjs';

const stack = await startStack({ extraEnv: { ASSET_REQUIRE_RIGHTS_CONFIRMATION: 'true' } });
const browser = await chromium.launch();
let failed = false;
try {
  const context = await browser.newContext(); await mockSupabase(context, USERS.owner);
  const page = await context.newPage();
  const { run, results } = makeRunner(page, stack);
  const state = {};
  const png = (shade) => ({ name: `img-${shade}.png`, mimeType: 'image/png', buffer: makePng(40, 30, [shade, 80, 120]) });
  const photo = () => page.locator('section[aria-label="Photo Engine 준비 작업실"]');
  const images = async () => (await apiCall(stack, USERS.owner.token, `/v1/assets?workspace_id=${state.workspace}&kind=image`)).body.items;
  const uploadedRights = async (assetId) => {
    const items = (await apiCall(stack, USERS.owner.token, `/v1/assets/${assetId}/provenance`)).body.items;
    return items.find(i => i.event_type === 'asset.uploaded').details.rights;
  };
  const rightsBoxes = () => photo().locator('fieldset.acs-photo-rights input[type=checkbox]');
  const alertText = async () => (await photo().locator('p[role=alert]').innerText({ timeout: 5000 }));

  await run('login and open the photo studio', async () => {
    await loginThroughUi(page, stack.webUrl, USERS.owner);
    state.workspace = await page.locator('.workspace-select').inputValue();
    await gotoPage(page, '포토 스튜디오');
    assert.equal(await rightsBoxes().count(), 2, 'rights and depicts-person checkboxes (consent appears only for a person)');
  });

  await run('without the rights checkbox the upload is refused with a clear message and nothing is stored', async () => {
    await photo().locator('input[type=file]').setInputFiles(png(10));
    assert.match(await alertText(), /권리 확인/);
    assert.equal((await images()).length, 0);
  });

  await run('with the rights checkbox the upload succeeds and the declaration is recorded in provenance', async () => {
    await photo().getByLabel(/사용할 권리가 있음을 확인/).check();
    await photo().locator('input[type=file]').setInputFiles(png(20));
    await photo().locator('select').first().locator('option', { hasText: 'img-20.png' }).waitFor({ state: 'attached' });
    const list = await images(); assert.equal(list.length, 1);
    assert.deepEqual(await uploadedRights(list[0].asset_id), { rights_confirmed: true, depicts_person: false, likeness_consent: false });
  });

  await run('a person is shown but consent is not checked: refused with the likeness message', async () => {
    await photo().getByLabel('이미지에 사람이 나옵니다').check();
    assert.equal(await rightsBoxes().count(), 3, 'consent checkbox appears once a person is declared');
    await photo().locator('input[type=file]').setInputFiles(png(30));
    assert.match(await alertText(), /동의 확인/);
    assert.equal((await images()).length, 1);
  });

  await run('person shown with consent: upload succeeds and consent is recorded', async () => {
    await photo().getByLabel(/동의를 받았음을 확인/).check();
    await photo().locator('input[type=file]').setInputFiles(png(40));
    await photo().locator('select').first().locator('option', { hasText: 'img-40.png' }).waitFor({ state: 'attached' });
    const list = await images(); assert.equal(list.length, 2);
    const newest = list.find(a => a.original_filename === 'img-40.png');
    assert.deepEqual(await uploadedRights(newest.asset_id), { rights_confirmed: true, depicts_person: true, likeness_consent: true });
  });

  await run('unchecking "a person is shown" hides and clears the consent so a stale consent is never sent', async () => {
    await photo().getByLabel('이미지에 사람이 나옵니다').uncheck();
    assert.equal(await rightsBoxes().count(), 2);
    await photo().locator('input[type=file]').setInputFiles(png(50));
    await photo().locator('select').first().locator('option', { hasText: 'img-50.png' }).waitFor({ state: 'attached' });
    const newest = (await images()).find(a => a.original_filename === 'img-50.png');
    assert.deepEqual(await uploadedRights(newest.asset_id), { rights_confirmed: true, depicts_person: false, likeness_consent: false });
  });

  console.log(`SUMMARY ${results.filter(r => r.ok).length}/${results.length} rights steps passed`);
} catch { failed = true; }
finally { await browser.close(); await stack.stop(); }
process.exit(failed ? 1 : 0);
