// Role, workspace-isolation and mobile checks in the browser (queue 12). Supabase Auth is mocked; no AI provider is called.
// Six scenarios: viewer, editor, owner, outsider (API), outsider (UI), mobile width.
import assert from 'node:assert/strict';
import { startStack, chromium, makePng, loginThroughUi, gotoPage, newUserPage, seedSharedWorkspace, makeRunner, apiCall, USERS } from './harness.mjs';

const stack = await startStack();
const browser = await chromium.launch();
let failed = false;
const all = [];
try {
  const seed = await seedSharedWorkspace(stack);
  const reviewStatus = async () => (await apiCall(stack, USERS.owner.token, `/v1/photo-drafts/${seed.draftId}/runs/${seed.runId}/review?workspace_id=${seed.workspace}`)).body.status;
  const imageCount = async () => (await apiCall(stack, USERS.owner.token, `/v1/assets?workspace_id=${seed.workspace}&kind=image`)).body.items.length;
  const photoSection = (page) => page.locator('section[aria-label="Photo Engine 준비 작업실"]');
  const goPhoto = async (page, who) => { await loginThroughUi(page, stack.webUrl, who); await gotoPage(page, '포토 스튜디오'); };
  const showsSharedWorkspace = async (page) => assert.equal(await page.locator('.workspace-select').inputValue(), seed.workspace);

  // 1) viewer: sees the shared workspace, cannot add images, cannot approve
  { const { context, page } = await newUserPage(browser, USERS.viewer); const { run, results } = makeRunner(page, stack);
    await run('1 viewer: sees the shared workspace but cannot upload or approve', async () => {
      await goPhoto(page, USERS.viewer); await showsSharedWorkspace(page);
      const before = await imageCount();
      await photoSection(page).locator('input[type=file]').setInputFiles({ name: 'viewer-upload.png', mimeType: 'image/png', buffer: makePng(40, 30, [1, 2, 3]) });
      await photoSection(page).locator('p[role=alert]').waitFor({ timeout: 8000 });
      assert.equal(await imageCount(), before, 'a viewer upload must not create an asset');
      assert.equal(await reviewStatus(), 'pending_review', 'review starts pending');
      const direct = await apiCall(stack, USERS.viewer.token, `/v1/photo-drafts/${seed.draftId}/runs/${seed.runId}/review/approve?workspace_id=${seed.workspace}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      assert.equal(direct.status, 403); assert.equal(await reviewStatus(), 'pending_review');
    }); all.push(...results); await context.close(); }

  // 2) editor: can upload, cannot approve (owner/admin only)
  { const { context, page } = await newUserPage(browser, USERS.editor); const { run, results } = makeRunner(page, stack);
    await run('2 editor: can upload an image but cannot approve a review', async () => {
      await goPhoto(page, USERS.editor); await showsSharedWorkspace(page);
      const before = await imageCount();
      await photoSection(page).locator('input[type=file]').setInputFiles({ name: 'editor-upload.png', mimeType: 'image/png', buffer: makePng(40, 30, [9, 9, 9]) });
      await photoSection(page).locator('select').first().locator('option', { hasText: /^editor-upload\.png$/ }).waitFor({ state: 'attached' });
      assert.equal(await imageCount(), before + 1);
      const denied = await apiCall(stack, USERS.editor.token, `/v1/photo-drafts/${seed.draftId}/runs/${seed.runId}/review/approve?workspace_id=${seed.workspace}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      assert.equal(denied.status, 403, 'editor must not approve'); assert.equal(await reviewStatus(), 'pending_review');
    }); all.push(...results); await context.close(); }

  // 3) owner approves in the UI
  { const { context, page } = await newUserPage(browser, USERS.owner); const { run, results } = makeRunner(page, stack);
    await run('3 owner: approves the review in the UI', async () => {
      await goPhoto(page, USERS.owner);
      await page.locator('.workspace-select').selectOption(seed.workspace);
      await page.getByRole('button', { name: /승인/ }).first().click();
      await page.waitForResponse(r => r.url().includes('/review/approve') && r.status() === 200, { timeout: 10000 });
      assert.equal(await reviewStatus(), 'approved');
    }); all.push(...results); await context.close(); }

  // 4) outsider through the API: no access to another workspace's data
  { const { context, page } = await newUserPage(browser, USERS.outsider); const { run, results } = makeRunner(page, stack);
    await run('4 outsider (API): the shared workspace looks nonexistent for every read and write', async () => {
      const t = USERS.outsider.token;
      const checks = [
        [`/v1/assets?workspace_id=${seed.workspace}&kind=image`, 'GET'],
        [`/v1/photo-drafts?workspace_id=${seed.workspace}`, 'GET'],
        [`/v1/products?workspace_id=${seed.workspace}`, 'GET'],
        [`/v1/photo-drafts/${seed.draftId}/runs?workspace_id=${seed.workspace}`, 'GET'],
        [`/v1/assets/${seed.assetId}`, 'GET'],
      ];
      for (const [path, method] of checks) { const r = await apiCall(stack, t, path, { method }); assert.ok([403, 404].includes(r.status), `${method} ${path} -> ${r.status}`); }
      const approve = await apiCall(stack, t, `/v1/photo-drafts/${seed.draftId}/runs/${seed.runId}/review/approve?workspace_id=${seed.workspace}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      assert.ok([403, 404].includes(approve.status), 'approve -> ' + approve.status);
      const form = new FormData(); form.set('workspace_id', seed.workspace); form.set('file', new Blob([makePng(30, 30, [5, 5, 5])], { type: 'image/png' }), 'x.png');
      const up = await fetch(stack.apiUrl + '/v1/assets/images', { method: 'POST', headers: { Authorization: `Bearer ${t}` }, body: form });
      assert.ok([403, 404].includes(up.status), 'upload -> ' + up.status);
    }); all.push(...results); await context.close(); }

  // 5) outsider in the UI: gets an own workspace and sees none of the shared data
  { const { context, page } = await newUserPage(browser, USERS.outsider); const { run, results } = makeRunner(page, stack);
    await run('5 outsider (UI): lands in an own empty workspace and sees none of the shared images or drafts', async () => {
      await goPhoto(page, USERS.outsider);
      assert.notEqual(await page.locator('.workspace-select').inputValue(), seed.workspace);
      const options = await page.locator('.workspace-select option').evaluateAll(os => os.map(o => o.value));
      assert.ok(!options.includes(seed.workspace), 'the shared workspace must not be listed');
      const imgOptions = await photoSection(page).locator('label', { hasText: '원본 이미지' }).locator('select option').allTextContents();
      assert.deepEqual(imgOptions, ['이미지를 선택하세요']);
      assert.match(await photoSection(page).innerText(), /저장된 초안이 없습니다/);
    }); all.push(...results); await context.close(); }

  // 6) mobile width
  { const { context, page } = await newUserPage(browser, USERS.owner, { viewport: { width: 390, height: 844 } }); const { run, results } = makeRunner(page, stack);
    await run('6 mobile 390px: login works, the photo studio is usable and the page does not scroll sideways', async () => {
      await goPhoto(page, USERS.owner);
      await page.locator('.workspace-select').selectOption(seed.workspace);
      await photoSection(page).waitFor();
      const overflow = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, inner: window.innerWidth }));
      assert.ok(overflow.scroll <= overflow.inner + 1, `horizontal overflow: ${overflow.scroll} > ${overflow.inner}`);
      assert.ok(await photoSection(page).locator('input[type=file]').count() === 1);
      const box = await photoSection(page).locator('label', { hasText: '원본 이미지' }).locator('select').boundingBox();
      assert.ok(box && box.width > 120 && box.x >= 0 && box.x + box.width <= 390 + 1, 'the source image select must fit the screen: ' + JSON.stringify(box));
    }); all.push(...results); await context.close(); }

  console.log(`SUMMARY ${all.filter(r => r.ok).length}/${all.length} role scenarios passed`);
} catch (error) { if (!all.some(r => r.ok === false)) console.log("ERROR " + (error && error.stack || error)); failed = true; }
finally { await browser.close(); await stack.stop(); }
process.exit(failed ? 1 : 0);
