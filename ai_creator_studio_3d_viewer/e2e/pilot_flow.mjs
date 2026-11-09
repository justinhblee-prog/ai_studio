// Pilot flow: login -> workspace -> image upload -> product -> photo draft -> local (deterministic, no AI) processing
// -> review approval -> manifest -> lookbook draft -> assembly -> approval -> ZIP export.
import assert from 'node:assert/strict';
import { startStack, chromium, mockSupabase, loginThroughUi, gotoPage, makePng, makeRunner, apiCall, USERS } from './harness.mjs';

const stack = await startStack();
const browser = await chromium.launch();
let failed = false;
try {
  const context = await browser.newContext({ acceptDownloads: true }); await mockSupabase(context, USERS.owner);
  const page = await context.newPage();
  page.on('dialog', d => d.accept());
  const { run, results } = makeRunner(page, stack);
  const state = {};

  await run('login through the UI (Supabase mocked) creates a workspace', async () => {
    await loginThroughUi(page, stack.webUrl, USERS.owner, { beforeSubmit: async () => {
      assert.equal(await page.locator('input[type=url]').count(), 0, 'sign-in screen of a release build must not offer an API address input');
      assert.equal(await page.locator('text=Backend API 주소').count(), 0);
    } });
    state.workspace = await page.locator('.workspace-select').inputValue();
    assert.match(state.workspace, /^ws_/);
    await page.getByRole('button', { name: /설정/ }).click();
    await page.locator('section.settings').waitFor();
    assert.equal(await page.locator('section.settings > label input').count(), 3, 'the connection fields are only user, workspace and job (the account panel below has its own controls)');
    assert.equal(await page.locator('section.settings', { hasText: 'Backend API 주소' }).count(), 0, 'settings panel must not offer an API address input');
    await page.getByRole('button', { name: /설정/ }).click();
  });

  const photo = page.locator('section[aria-label="Photo Engine 준비 작업실"]');
  await run('upload a product image in the photo studio', async () => {
    await gotoPage(page, '포토 스튜디오');
    await photo.getByLabel(/사용할 권리가 있음을 확인/).check(); // uploads must declare rights by default (D2)
    await photo.locator('input[type=file]').setInputFiles({ name: 'shirt.png', mimeType: 'image/png', buffer: makePng(48, 32, [200, 40, 40]) });
    await photo.locator('select').first().locator('option', { hasText: 'shirt.png' }).waitFor({ state: 'attached' });
    const assets = await apiCall(stack, USERS.owner.token, `/v1/assets?workspace_id=${state.workspace}&kind=image`);
    assert.equal(assets.status, 200); assert.equal(assets.body.items.length, 1);
    state.assetId = assets.body.items[0].asset_id;
  });

  await run('create a catalog product with that image', async () => {
    await gotoPage(page, '상품 카탈로그');
    const cat = page.locator('section[aria-label="상품 SKU 카탈로그"]');
    await cat.getByLabel('SKU', { exact: true }).fill('E2E-SHIRT-001');
    await cat.locator('label', { hasText: '상품명' }).locator('input').fill('E2E Shirt');
    await cat.locator('label', { hasText: '카테고리' }).locator('input').fill('shirt');
    await cat.locator('label', { hasText: '상품 이미지' }).locator('select').selectOption({ label: 'shirt.png' });
    await cat.getByRole('button', { name: /^상품 (등록|추가|생성|저장)/ }).click();
    await page.locator('[aria-label="등록된 상품"]', { hasText: 'E2E-SHIRT-001' }).waitFor({ timeout: 10000 });
    const products = await apiCall(stack, USERS.owner.token, `/v1/products?workspace_id=${state.workspace}`);
    assert.equal(products.body.items.length, 1); state.productId = products.body.items[0].product_id;
  });

  await run('save a photo draft for the product image', async () => {
    await gotoPage(page, '포토 스튜디오');
    await photo.locator('label', { hasText: '원본 이미지' }).locator('select').selectOption({ label: 'shirt.png' });
    await photo.locator('label', { hasText: '편집 작업' }).locator('select').selectOption({ label: '품질 향상' });
    // The "saved drafts" list is on screen even with zero drafts, so wait for the save request itself, not for the list.
    await Promise.all([
      page.waitForResponse(r => r.url().includes('/v1/photo-drafts') && r.request().method() === 'POST' && r.status() === 201, { timeout: 10000 }),
      photo.getByRole('button', { name: 'Photo Draft 초안 저장' }).click(),
    ]);
    await page.locator('[aria-label="저장된 Photo Draft"]').waitFor({ timeout: 10000 });
    const drafts = await apiCall(stack, USERS.owner.token, `/v1/photo-drafts?workspace_id=${state.workspace}`);
    assert.equal(drafts.body.items.length, 1); state.draftId = drafts.body.items[0].draft_id;
  });

  await run('run deterministic local processing (no provider, no AI) and see one succeeded run', async () => {
    await page.getByRole('button', { name: /로컬 이미지/ }).click();
    await page.waitForResponse(r => r.url().includes('/process-local') && r.status() === 200, { timeout: 20000 });
    const runs = await apiCall(stack, USERS.owner.token, `/v1/photo-drafts/${state.draftId}/runs?workspace_id=${state.workspace}`);
    assert.equal(runs.status, 200);
    const items = runs.body.items || runs.body.runs || [];
    assert.equal(items.length, 1); assert.equal(items[0].status, 'succeeded');
    state.runId = items[0].run_id;
  });

  await run('approve the output in the review UI and export the manifest', async () => {
    await page.getByRole('button', { name: /승인/ }).first().click();
    await page.waitForResponse(r => r.url().includes('/review/approve') && r.status() === 200, { timeout: 10000 });
    await page.getByRole('button', { name: /manifest/i }).first().click();
    await page.waitForResponse(r => r.url().includes('/export-manifest') && r.status() === 200, { timeout: 10000 });
    const review = await apiCall(stack, USERS.owner.token, `/v1/photo-drafts/${state.draftId}/runs/${state.runId}/review?workspace_id=${state.workspace}`);
    assert.equal(review.status, 200); assert.equal(review.body.status, 'approved');
  });

  const lookbook = page.locator('section[aria-label="Lookbook 준비 작업실"]');
  await run('save a lookbook draft from the catalog product', async () => {
    await gotoPage(page, '룩북 스튜디오');
    await lookbook.locator('label', { hasText: '초안 이름' }).locator('input').fill('E2E Lookbook');
    await lookbook.locator('label', { hasText: '카탈로그 상품' }).locator('select').selectOption({ index: 0 });
    await lookbook.getByRole('button', { name: 'Lookbook 초안 저장' }).click();
    await page.locator('[aria-label="저장된 Lookbook 초안"]', { hasText: 'E2E Lookbook' }).waitFor({ timeout: 10000 });
    const list = await apiCall(stack, USERS.owner.token, `/v1/lookbook-drafts?workspace_id=${state.workspace}`);
    assert.equal(list.body.items.length, 1); state.lookbookId = list.body.items[0].draft_id;
  });

  await run('submit and approve the lookbook plan', async () => {
    const saved = page.locator('[aria-label="저장된 Lookbook 초안"]');
    await saved.getByRole('button', { name: /검토 요청|제출/ }).first().click();
    await page.waitForResponse(r => r.url().includes('/submit') && r.status() === 200, { timeout: 10000 });
    await saved.getByRole('button', { name: /^승인$|기획 승인|초안 승인/ }).first().click();
    await page.waitForResponse(r => /\/approve$/.test(new URL(r.url()).pathname) && r.status() === 200, { timeout: 10000 });
    const draft = await apiCall(stack, USERS.owner.token, `/v1/lookbook-drafts/${state.lookbookId}?workspace_id=${state.workspace}`);
    assert.equal(draft.status, 200); assert.equal(draft.body.workflow_status, 'approved');
  });

  await run('open assembly, attach the approved photo output, submit and approve the assembly', async () => {
    const saved = page.locator('[aria-label="저장된 Lookbook 초안"]');
    await saved.getByRole('button', { name: '승인 Photo 결과 연결' }).click();
    const assembly = page.locator('[aria-label="승인된 Photo 결과 조립"]');
    await assembly.waitFor({ timeout: 10000 });
    await assembly.locator('label', { hasText: '승인된 Photo 결과' }).locator('select').selectOption({ index: 1 });
    await assembly.locator('label', { hasText: '캡션' }).locator('input').fill('Look 1');
    await assembly.getByRole('button', { name: /^Photo 결과/ }).click();
    await page.waitForResponse(r => /\/outputs$/.test(new URL(r.url()).pathname) && r.request().method() === 'POST' && r.status() === 201, { timeout: 10000 });
    await assembly.getByRole('button', { name: '조립 검토 요청' }).click();
    await page.waitForResponse(r => r.url().includes('/outputs/submit') && r.status() === 200, { timeout: 10000 });
    await assembly.getByRole('button', { name: /^조립 승인/ }).click();
    await page.waitForResponse(r => r.url().includes('/outputs/approve') && r.status() === 200, { timeout: 10000 });
    const review = await apiCall(stack, USERS.owner.token, `/v1/lookbook-drafts/${state.lookbookId}/outputs/review?workspace_id=${state.workspace}`);
    assert.equal(review.status, 200); assert.equal(review.body.status, 'approved');
  });

  await run('create the internal ZIP package and download it; the ZIP is a real archive', async () => {
    const assembly = page.locator('[aria-label="승인된 Photo 결과 조립"]');
    await assembly.getByRole('button', { name: '승인된 Lookbook 내부 ZIP 만들기' }).click();
    await page.waitForResponse(r => r.url().includes('/package-export') && r.request().method() === 'POST' && r.status() === 200, { timeout: 20000 });
    const exports = await apiCall(stack, USERS.owner.token, `/v1/lookbook-drafts/${state.lookbookId}/outputs/exports?workspace_id=${state.workspace}`);
    assert.equal(exports.status, 200); assert.equal((exports.body.items || []).length >= 1, true);
    const dlButton = assembly.getByRole('button', { name: /ZIP 다운로드/ });
    const [download] = await Promise.all([page.waitForEvent('download', { timeout: 20000 }), dlButton.first().click()]);
    const path = await download.path();
    const { readFileSync } = await import('node:fs');
    const bytes = readFileSync(path);
    assert.equal(bytes.subarray(0, 2).toString(), 'PK', 'downloaded file must be a ZIP archive');
    assert.ok(bytes.length > 200, 'ZIP must not be empty');
    state.zipBytes = bytes.length;
    const { spawnSync } = await import('node:child_process');
    const listing = spawnSync('python', ['-c', 'import sys,zipfile;z=zipfile.ZipFile(sys.argv[1]);assert z.testzip() is None;print("\\n".join(sorted(z.namelist())))', path], { encoding: 'utf8' });
    assert.equal(listing.status, 0, listing.stderr);
    state.zipEntries = listing.stdout.trim().split('\n');
    assert.ok(state.zipEntries.some(n => /manifest/i.test(n)), 'ZIP must contain a manifest: ' + state.zipEntries.join(','));
    assert.ok(state.zipEntries.some(n => /\.(png|jpe?g|webp)$/i.test(n)), 'ZIP must contain the approved image: ' + state.zipEntries.join(','));
    const read = spawnSync('python', ['-c', 'import sys,zipfile;print(zipfile.ZipFile(sys.argv[1]).read("manifest.json").decode())', path], { encoding: 'utf8' });
    assert.equal(read.status, 0, read.stderr);
    state.zipManifest = JSON.parse(read.stdout);
    assert.equal(state.zipManifest.is_ai_generated, false, 'the package built from local adjustments must say it is not AI generated');
    assert.equal(state.zipManifest.publication_authorized, false);
  });

  console.log(`SUMMARY ${results.filter(r => r.ok).length}/${results.length} steps passed; zip ${state.zipBytes} bytes, entries: ${state.zipEntries.join(', ')}`);
} catch { failed = true; }
finally { await browser.close(); await stack.stop(); }
process.exit(failed ? 1 : 0);
