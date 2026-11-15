// R-033 in the browser: the Library screen, the "내 자산 / 라이브러리" tabs in the pickers, the AI label, failure text.
// Real: web bundle, backend (PROVIDER_MODE=mock), SQLite, library files. Mocked: Supabase Auth. No AI provider is called.
import assert from 'node:assert/strict';
import { startStack, chromium, mockSupabase, loginThroughUi, gotoPage, makeRunner, apiCall, seedLibrary, USERS } from './harness.mjs';

const stack = await startStack();
const browser = await chromium.launch();
let failed = false;
try {
  seedLibrary(stack);
  const context = await browser.newContext(); await mockSupabase(context, USERS.owner);
  const page = await context.newPage();
  const { run, results } = makeRunner(page, stack);
  const state = {};
  const screen = () => page.locator('section[aria-label="라이브러리"]');
  const cards = () => screen().locator('ul[aria-label="라이브러리 항목"] li');
  const assets = async () => (await apiCall(stack, USERS.owner.token, `/v1/assets?workspace_id=${state.workspace}&kind=image`)).body.items;

  await run('the Library screen lists the published models, each labelled "AI 생성 이미지" with a real picture; draft and retired items are absent', async () => {
    await loginThroughUi(page, stack.webUrl, USERS.owner);
    state.workspace = await page.locator('.workspace-select').inputValue();
    // "라이브러리" is also part of "에셋 라이브러리", so the shared gotoPage would match two menu buttons
    await page.locator('button.nav', { hasText: '라이브러리' }).filter({ hasNotText: '에셋' }).click();
    await cards().first().waitFor({ timeout: 15000 });
    assert.equal(await cards().count(), 2);
    for (const text of await cards().allInnerTexts()) assert.match(text, /AI 생성 이미지/);
    await cards().first().locator('img').waitFor({ timeout: 10000 });
    // the <img> exists as soon as its address is known; wait until the browser has really decoded it
    await page.waitForFunction(() => { const i = document.querySelector('ul[aria-label="라이브러리 항목"] li img'); return !!i && i.complete && i.naturalWidth > 0; }, null, { timeout: 10000 });
    const all = await screen().innerText();
    assert.doesNotMatch(all, /초안 셔츠|내린 셔츠/);
  });

  await run('model filters narrow the list; a search with no match shows the empty text', async () => {
    await screen().getByLabel('머리').selectOption('wavy');
    await page.waitForFunction(() => document.querySelectorAll('ul[aria-label="라이브러리 항목"] li').length === 1, null, { timeout: 10000 });
    assert.match(await cards().first().innerText(), /샘플 모델 1/);
    await screen().getByLabel('머리').selectOption('');
    await screen().getByLabel('검색').fill('없는이름zzz');
    await screen().getByRole('button', { name: '검색' }).click();
    await screen().getByText('이 조건에 맞는 라이브러리 항목이 없습니다.').waitFor({ timeout: 10000 });
  });

  await run('clothes tab: using an item copies it into my assets and says so; the original stays in the library', async () => {
    await screen().getByRole('tab', { name: '의류' }).click();
    await cards().first().waitFor({ timeout: 10000 });
    assert.equal(await cards().count(), 2, 'tops only: draft/retired hidden');
    assert.deepEqual(await assets(), []);
    await cards().filter({ hasText: '샘플 셔츠' }).getByRole('button', { name: '내 작업에 가져오기' }).click();
    await screen().getByText(/내 자산에 가져왔습니다/).waitFor({ timeout: 10000 });
    const mine = await assets();
    assert.equal(mine.length, 1); assert.match(mine[0].original_filename, /top-01/);
    assert.equal((await apiCall(stack, USERS.owner.token, '/v1/library/items/top-01')).status, 200);
  });

  await run('a failing library shows a Korean message with a retry button, then recovers', async () => {
    await page.route(/\/v1\/library\/items\?/, route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Service Unavailable' }) }));
    await screen().getByRole('tab', { name: '액세서리' }).click();
    const alert = screen().locator('[role=alert]').filter({ hasText: '라이브러리를 불러오지 못했습니다' });
    await alert.waitFor({ timeout: 10000 });
    assert.doesNotMatch(await alert.innerText(), /Service Unavailable/);
    await page.unroute(/\/v1\/library\/items\?/);
    await alert.getByRole('button', { name: '다시 시도' }).click();
    await cards().first().waitFor({ timeout: 10000 });
    assert.match(await cards().first().innerText(), /샘플 토트백/);
  });

  await run('generation start: tabs 내 자산 / 라이브러리, upload stays visible first, a library model is copied and selected', async () => {
    await gotoPage(page, '가상 착장 시험 생성');
    const gen = page.locator('section[aria-label="가상 착장 생성 시작"]');
    await gen.getByRole('tab', { name: '내 자산' }).first().waitFor({ timeout: 10000 });
    assert.equal(await gen.getByLabel('모델 사진 올리기').isVisible(), true, 'my-photo upload is visible without opening the library');
    const group = gen.getByRole('group', { name: '모델 사진 고르기' });
    await group.getByRole('tab', { name: '라이브러리' }).click();
    await group.locator('ul[aria-label="라이브러리 항목"] li').first().waitFor({ timeout: 10000 });
    assert.equal(await group.locator('ul[aria-label="라이브러리 항목"] li').count(), 2, 'only models are offered for the model photo');
    await group.locator('ul[aria-label="라이브러리 항목"] li').filter({ hasText: '샘플 모델 1' }).getByRole('button', { name: '가져와서 선택' }).click();
    await group.locator('select').first().waitFor({ state: 'visible', timeout: 10000 });  // back on 내 자산
    const chosen = await group.locator('select').first().inputValue();
    const mine = await assets();
    assert.ok(mine.some(a => a.asset_id === chosen && /model-01/.test(a.original_filename)), 'the copy is selected');
  });

  await run('photo studio: the source picker has the same tabs and the upload button is still in the header', async () => {
    await gotoPage(page, '포토 스튜디오');
    const photo = page.locator('section[aria-label="Photo Engine 준비 작업실"]');
    assert.equal(await photo.getByText('이미지 추가').first().isVisible(), true);
    const group = photo.getByRole('group', { name: '원본 이미지 고르기' });
    await group.getByRole('tab', { name: '라이브러리' }).click();
    await group.locator('ul[aria-label="라이브러리 항목"] li').first().waitFor({ timeout: 10000 });
    await group.getByRole('button', { name: '배경', exact: true }).click();  // the photo studio offers every category as chips
    await group.locator('ul[aria-label="라이브러리 항목"] li').filter({ hasText: '샘플 스튜디오' }).getByRole('button', { name: '가져와서 선택' }).click();
    await group.locator('select').first().waitFor({ state: 'visible', timeout: 10000 });
    const chosen = await group.locator('select').first().inputValue();
    assert.ok((await assets()).some(a => a.asset_id === chosen && /background-01/.test(a.original_filename)));
  });

  console.log(`SUMMARY ${results.filter(r => r.ok).length}/${results.length} library steps passed`);
} catch { failed = true; }
finally { await browser.close(); await stack.stop(); }
process.exit(failed ? 1 : 0);
