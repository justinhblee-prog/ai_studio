// R-039 in the browser: brand model profiles. Real: web bundle, backend (FEATURE_CHARACTER=1), SQLite, library files. Mocked: Supabase Auth.
import assert from 'node:assert/strict';
import { startStack, chromium, mockSupabase, loginThroughUi, gotoPage, makeRunner, apiCall, seedLibrary, makePng, USERS } from './harness.mjs';

const stack = await startStack({ extraEnv: { FEATURE_CHARACTER: '1' } });
const browser = await chromium.launch();
let failed = false;
try {
  seedLibrary(stack);
  const context = await browser.newContext(); await mockSupabase(context, USERS.owner);
  const page = await context.newPage();
  const { run, results } = makeRunner(page, stack);
  const state = {};
  const screen = () => page.locator('section[aria-label="캐릭터 프로필"]');
  const list = () => screen().locator('ul[aria-label="프로필 목록"] li');
  const chars = async () => (await apiCall(stack, USERS.owner.token, `/v1/workspaces/${state.workspace}/characters`)).body.items;

  await run('the screen opens empty and the service is on', async () => {
    await loginThroughUi(page, stack.webUrl, USERS.owner);
    state.workspace = await page.locator('.workspace-select').inputValue();
    await gotoPage(page, '캐릭터');
    await screen().getByText('아직 프로필이 없습니다.').waitFor({ timeout: 10000 });
    assert.equal(await screen().getByText('파일럿 시험판').count(), 0);
  });

  await run('a profile made from a library model gets its attributes, one reference image (the copy), and the copy is in my assets', async () => {
    const card = screen().locator('ul[aria-label="라이브러리 항목"] li').filter({ hasText: '샘플 모델 1' });
    await card.waitFor({ timeout: 10000 });
    await card.getByRole('button', { name: '프로필 만들기' }).click();
    await list().first().waitFor({ timeout: 15000 });
    const text = await list().first().innerText();
    for (const part of ['샘플 모델 1', '30대', '웨이브', '피부색 3단계', '지역 느낌 유럽', '기준 이미지 1장']) assert.ok(text.includes(part), part);
    const made = await chars();
    assert.equal(made.length, 1); assert.equal(made[0].asset_ids.length, 1);
    const assets = (await apiCall(stack, USERS.owner.token, `/v1/assets?workspace_id=${state.workspace}&kind=image`)).body.items;
    assert.ok(assets.some(a => a.asset_id === made[0].asset_ids[0] && /model-01/.test(a.original_filename)));
  });

  await run('a profile from my own images needs a name and 1-5 distinct images; the 6th image cannot be ticked', async () => {
    for (let i = 0; i < 6; i += 1) {
      const r = await fetch(`${stack.apiUrl}/v1/assets/images`, { method: 'POST', headers: { Authorization: `Bearer ${USERS.owner.token}` },
        body: (() => { const f = new FormData(); f.set('workspace_id', state.workspace); f.set('rights_confirmed', 'true'); f.set('file', new Blob([makePng(30, 30, [i * 30, 90, 150])], { type: 'image/png' }), `mine-${i}.png`); return f; })() });
      assert.equal(r.status, 201, await r.text());
    }
    await page.reload(); await page.locator('.workspace-select').waitFor({ timeout: 20000 });
    await gotoPage(page, '캐릭터');
    const form = screen().locator('form[aria-label="내 사진으로 프로필 만들기"]');
    await form.getByRole('checkbox').first().waitFor({ timeout: 10000 });
    const submit = form.getByRole('button', { name: '프로필 만들기' });
    assert.equal(await submit.isDisabled(), true, 'nothing chosen yet');
    await form.getByLabel('프로필 이름').fill('내 브랜드 모델');
    assert.equal(await submit.isDisabled(), true, 'no image yet');
    const boxes = form.getByRole('checkbox');
    for (let i = 0; i < 5; i += 1) await boxes.nth(i).check();
    assert.equal(await boxes.nth(5).isDisabled(), true, 'at most 5 reference images');
    assert.equal(await submit.isDisabled(), false);
    await submit.click();
    await screen().getByText(/"내 브랜드 모델" 프로필을 만들었습니다/).waitFor({ timeout: 10000 });
    const made = await chars();
    assert.equal(made.length, 2); assert.equal(made.find(c => c.identity.name === '내 브랜드 모델').asset_ids.length, 5);
  });

  await run('deleting asks twice, and the profile is gone afterwards', async () => {
    const before = (await chars()).length;   // the server's count, not the screen's: the list re-reads after the "created" message shows
    await page.waitForFunction(n => document.querySelectorAll('ul[aria-label="프로필 목록"] li').length === n, before, { timeout: 10000 });
    await list().filter({ hasText: '내 브랜드 모델' }).getByRole('button', { name: '삭제' }).click();
    assert.equal(await chars().then(c => c.length), before, 'one click does not delete');
    await list().filter({ hasText: '내 브랜드 모델' }).getByRole('button', { name: '정말 삭제' }).click();
    await page.waitForFunction(n => document.querySelectorAll('ul[aria-label="프로필 목록"] li').length === n, before - 1, { timeout: 10000 });
    assert.equal((await chars()).length, before - 1);
  });

  await run('with the service switched off the screen says so and refuses to create (the list stays readable)', async () => {
    await page.route(/\/v1\/features$/, route => route.fulfill({ status: 200, contentType: 'application/json', headers: { 'access-control-allow-origin': '*' },
      body: JSON.stringify({ features: { character: { enabled: false, status: 'pilot_preview' } } }) }));
    await page.reload(); await page.locator('.workspace-select').waitFor({ timeout: 20000 });
    await gotoPage(page, '캐릭터');
    await screen().getByText('파일럿 시험판').waitFor({ timeout: 10000 });
    assert.equal(await screen().getByRole('button', { name: '프로필 만들기' }).first().isDisabled(), true);
    assert.equal(await screen().locator('form[aria-label="내 사진으로 프로필 만들기"]').getByLabel('프로필 이름').isDisabled(), true);
    assert.ok(await list().count() >= 1, 'existing profiles can still be seen');
  });

  console.log(`SUMMARY ${results.filter(r => r.ok).length}/${results.length} character steps passed`);
} catch { failed = true; }
finally { await browser.close(); await stack.stop(); }
process.exit(failed ? 1 : 0);
