// R-026 in the browser: the try-on generation start screen (mock provider only, no external call).
// Real: web bundle (built with VITE_ASSET_PUBLIC_BASE_URL), backend (PROVIDER_MODE=mock), SQLite. Mocked: Supabase Auth.
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
  const png = (shade) => ({ name: `gen-${shade}.png`, mimeType: 'image/png', buffer: makePng(40, 30, [shade, 80, 120]) });
  const screen = () => page.locator('section[aria-label="가상 착장 생성 시작"]');
  const jobs = async () => (await apiCall(stack, USERS.owner.token, `/v1/generation-jobs?workspace_id=${state.workspace}`)).body;
  const upload = async (label, shade) => {
    await screen().getByLabel(`${label} 올리기`).setInputFiles(png(shade));
    await screen().locator('select').first().locator('option', { hasText: `gen-${shade}.png` }).waitFor({ state: 'attached' });
  };

  await run('the screen opens, says it is a test generation, and is ready because the public address is built in', async () => {
    await loginThroughUi(page, stack.webUrl, USERS.owner);
    state.workspace = await page.locator('.workspace-select').inputValue();
    await gotoPage(page, '가상 착장 시험 생성');
    const text = await screen().innerText();
    assert.match(text, /시험 생성/);
    assert.match(text, /mock/);
    assert.doesNotMatch(text, /생성 준비 중입니다/);
    assert.equal(await screen().getByRole('button', { name: '시험 생성 시작' }).isDisabled(), true, 'nothing is chosen yet');
  });

  await run('an upload without the rights checkbox is refused and stores nothing', async () => {
    await screen().getByLabel('모델 사진 올리기').setInputFiles(png(10));
    assert.match(await screen().locator('[role=alert]').first().innerText({ timeout: 5000 }), /권리 확인/);
    assert.equal((await apiCall(stack, USERS.owner.token, `/v1/assets?workspace_id=${state.workspace}&kind=image`)).body.items.length, 0);
  });

  await run('with the rights checkbox both images upload and are preselected', async () => {
    await screen().getByLabel(/사용할 권리가 있음을 확인/).check();
    await upload('모델 사진', 20);
    await upload('의류 사진', 30);
    assert.equal(await screen().getByRole('button', { name: '시험 생성 시작' }).isDisabled(), false);
  });

  await run('starting creates exactly one mock job and shows its id; the job is readable via the API', async () => {
    await screen().getByLabel('의류 종류').selectOption('tops');
    await screen().getByLabel('품질 모드').selectOption('quality');
    await screen().getByRole('button', { name: '시험 생성 시작' }).click();
    const status = screen().locator('[aria-label="생성 작업 상태"]');
    await status.waitFor({ timeout: 15000 });
    assert.match(await status.innerText(), /job_[0-9a-f]+/);
    assert.match(await status.innerText(), /mock/);
    const list = await jobs();
    const items = Array.isArray(list) ? list : list.items;
    assert.equal(items.length, 1);
    assert.equal(items[0].provider, 'mock');
    state.jobId = items[0].job_id;
  });

  await run('the status refresh works and a second click makes a second job (new idempotency key)', async () => {
    await screen().getByRole('button', { name: '상태 새로고침' }).click();
    await screen().locator('[aria-label="생성 작업 상태"]').getByText(state.jobId).waitFor({ timeout: 10000 });
    await screen().getByRole('button', { name: '시험 생성 시작' }).click();
    // wait for a NEW job id to be shown (the status block disappears while the request is in flight, so absence is not enough)
    await page.waitForFunction((id) => { const t = document.querySelector('[aria-label="생성 작업 상태"]')?.textContent || ''; return /job_[0-9a-f]+/.test(t) && !t.includes(id); }, state.jobId, { timeout: 15000 });
    const list = await jobs();
    assert.equal((Array.isArray(list) ? list : list.items).length, 2);
  });

  console.log(`SUMMARY ${results.filter(r => r.ok).length}/${results.length} generation steps passed`);
} catch { failed = true; }
finally { await browser.close(); await stack.stop(); }
process.exit(failed ? 1 : 0);
