// R-030 A in the browser: the server stops accepting the login (401) -> the person is asked to sign in again ON TOP of the screen they
// were on; what they had typed is kept; after signing in they continue there. Real: web bundle, backend, SQLite. Mocked: Supabase Auth
// (its token refresh is not mocked, so the silent renewal fails exactly as it would with a revoked refresh token).
import assert from 'node:assert/strict';
import { startStack, chromium, mockSupabase, loginThroughUi, gotoPage, makeRunner, seedLibrary, USERS } from './harness.mjs';

const stack = await startStack();
const browser = await chromium.launch();
let failed = false;
try {
  seedLibrary(stack);
  const context = await browser.newContext(); await mockSupabase(context, USERS.owner);
  const page = await context.newPage();
  const { run, results } = makeRunner(page, stack);
  const gen = () => page.locator('section[aria-label="가상 착장 생성 시작"]');
  const dialog = () => page.getByRole('dialog', { name: '로그인이 만료되었습니다' });
  const cors = { 'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*' };
  const reject401 = route => (route.request().method() === 'OPTIONS'
    ? route.fulfill({ status: 204, headers: cors })
    : route.fulfill({ status: 401, contentType: 'application/json', headers: cors, body: JSON.stringify({ detail: 'Invalid bearer token' }) }));
  const TYPED = '작성 중이던 추가 요청 문구';

  await run('a 401 from the API opens a Korean sign-in dialog over the same screen and what was typed is still there', async () => {
    await loginThroughUi(page, stack.webUrl, USERS.owner);
    await gotoPage(page, '가상 착장 시험 생성');
    await gen().getByLabel(/추가 요청/).fill(TYPED);
    await page.route(`${stack.apiUrl}/v1/**`, reject401);
    await gen().getByRole('group', { name: '모델 사진 고르기' }).getByRole('tab', { name: '라이브러리' }).click();   // any API call will do
    await dialog().waitFor({ timeout: 15000 });
    const text = await dialog().innerText();
    assert.match(text, /로그인이 만료되었습니다/); assert.match(text, /작성 중이던 내용은 그대로 유지/);
    assert.doesNotMatch(text, /Invalid bearer token/, 'the server\'s English text is not shown');
    assert.equal(await gen().getByLabel(/추가 요청/).inputValue(), TYPED, 'the screen underneath kept the typed text');
    assert.equal(await page.locator('.auth-page, .public-landing').count(), 0, 'the person was not thrown out to the start page');
  });

  await run('signing in again closes the dialog, keeps the screen and the typed text, and the action works when repeated', async () => {
    await page.unroute(`${stack.apiUrl}/v1/**`, reject401);
    await dialog().getByLabel('비밀번호').fill('password-123');
    await dialog().getByRole('button', { name: '다시 로그인' }).click();
    await dialog().waitFor({ state: 'detached', timeout: 15000 });
    await page.getByText(/다시 로그인되었습니다/).waitFor({ timeout: 10000 });
    assert.equal(await gen().getByLabel(/추가 요청/).inputValue(), TYPED);
    assert.ok(await gen().isVisible(), 'still on the same screen');
    const group = gen().getByRole('group', { name: '모델 사진 고르기' });
    // the library list that failed with the 401 is still on screen with its own retry button: repeating the action now works
    await group.getByRole('button', { name: '다시 시도' }).click();
    await group.locator('ul[aria-label="라이브러리 항목"] li').first().waitFor({ timeout: 15000 });
  });

  await run('"로그아웃" in the dialog returns to the start screen', async () => {
    await page.route(`${stack.apiUrl}/v1/**`, reject401);
    await gen().getByRole('group', { name: '모델 사진 고르기' }).getByRole('tab', { name: '내 자산' }).click();
    await gotoPage(page, '생성 작업 결과');
    await dialog().waitFor({ timeout: 15000 });
    await page.unroute(`${stack.apiUrl}/v1/**`, reject401);
    await dialog().getByRole('button', { name: /로그아웃/ }).click();
    await page.getByRole('button', { name: '로그인' }).first().waitFor({ timeout: 15000 });
    assert.equal(await page.locator('.workspace-select').count(), 0);
  });

  console.log(`SUMMARY ${results.filter(r => r.ok).length}/${results.length} session steps passed`);
} catch { failed = true; }
finally { await browser.close(); await stack.stop(); }
process.exit(failed ? 1 : 0);
