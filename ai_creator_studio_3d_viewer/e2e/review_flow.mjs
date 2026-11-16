// Review decisions in the browser: change request, approve, reject on a seeded finished job output.
// Real: web bundle, backend, SQLite, asset-link worker. Mocked: Supabase Auth. The finished output is SEEDED (mock provider makes no image).
import assert from 'node:assert/strict';
import { startStack, chromium, mockSupabase, loginThroughUi, gotoPage, makeRunner, apiCall, seedFinishedJobOutput, USERS } from './harness.mjs';

const stack = await startStack();
const browser = await chromium.launch();
let failed = false;
try {
  const context = await browser.newContext(); await mockSupabase(context, USERS.owner);
  const page = await context.newPage();
  const { run, results } = makeRunner(page, stack);
  const state = {};
  const item = () => page.locator('article.acs-output-review-item').first();
  const status = async () => (await item().locator('.acs-output-review-heading span').innerText()).trim();
  const comment = () => page.getByLabel('검수 의견');
  const newJob = async () => {
    const created = await apiCall(stack, USERS.owner.token, '/v1/generation-jobs', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workspace_id: state.workspace, model_image_url: 'https://example.com/m.jpg', garment_image_url: 'https://example.com/g.jpg' }) });
    assert.equal(created.status, 202); seedFinishedJobOutput(stack, created.body.job_id); return created.body.job_id;
  };
  const open = async (jobId) => {
    await page.getByRole('button', { name: /설정/ }).click();
    await page.locator('section.settings label', { hasText: '결과 검수 Job ID' }).locator('input').fill(jobId);
    await page.getByRole('button', { name: /설정/ }).click();
    await gotoPage(page, '결과물 검수');
    await item().waitFor({ timeout: 15000 });
    await page.waitForFunction(() => !/loading/.test(document.querySelector('article.acs-output-review-item .acs-output-review-heading span')?.textContent || ''), null, { timeout: 15000 });
  };
  const events = async (jobId) => {
    const outputId = (await apiCall(stack, USERS.owner.token, `/v1/generation-jobs/${jobId}/outputs`)).body.data[0].id;
    return { outputId, review: (await apiCall(stack, USERS.owner.token, `/v1/generation-jobs/${jobId}/outputs/${outputId}/review`)).body };
  };

  await run('a new output waits for review; change request and rejection need a comment, approval does not', async () => {
    await loginThroughUi(page, stack.webUrl, USERS.owner);
    state.workspace = await page.locator('.workspace-select').inputValue();
    state.jobA = await newJob();
    await open(state.jobA);
    assert.equal(await status(), 'pending_review');
    assert.equal(await item().getByRole('button', { name: '수정 요청' }).isDisabled(), true);
    assert.equal(await item().getByRole('button', { name: '반려' }).isDisabled(), true);
    assert.equal(await item().getByRole('button', { name: '승인' }).isDisabled(), false);
  });

  await run('a change request with a comment moves it to changes_requested and is recorded; it can still be decided afterwards', async () => {
    await comment().fill('로고 색을 더 진하게');
    await item().getByRole('button', { name: '수정 요청' }).click();
    await page.waitForFunction(() => /changes_requested/.test(document.querySelector('article.acs-output-review-item .acs-output-review-heading span')?.textContent || ''), null, { timeout: 15000 });
    assert.match(await item().locator('ol.acs-output-review-history').innerText(), /changes_requested/);
    const { review } = await events(state.jobA);
    assert.equal(review.status, 'changes_requested');
    assert.ok(review.events.some(e => e.decision === 'changes_requested'));
    assert.equal(await item().getByRole('button', { name: '승인' }).isDisabled(), false, 'still reviewable');
    assert.equal(await comment().inputValue(), '', 'the comment box is cleared after saving');
  });

  await run('approval is final: the buttons disappear, a final-state note shows, and both events are in the history', async () => {
    await item().getByRole('button', { name: '승인' }).click();
    await page.waitForFunction(() => /approved/.test(document.querySelector('article.acs-output-review-item .acs-output-review-heading span')?.textContent || ''), null, { timeout: 15000 });
    await item().getByText('최종 상태입니다').waitFor();
    assert.equal(await item().getByRole('button', { name: '승인' }).count(), 0);
    const { outputId, review } = await events(state.jobA);
    assert.deepEqual(review.events.map(e => e.decision).sort(), ['approved', 'changes_requested']);
    const again = await apiCall(stack, USERS.owner.token, `/v1/generation-jobs/${state.jobA}/outputs/${outputId}/review/reject`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ comment: 'late' }) });
    assert.ok(again.status >= 400 && again.status < 500, `a decided output cannot be decided again (got ${again.status})`);
  });

  await run('rejection with a comment is final and recorded', async () => {
    state.jobB = await newJob();
    await open(state.jobB);
    await comment().fill('상품과 다른 제품');
    await item().getByRole('button', { name: '반려' }).click();
    await page.waitForFunction(() => /rejected/.test(document.querySelector('article.acs-output-review-item .acs-output-review-heading span')?.textContent || ''), null, { timeout: 15000 });
    await item().getByText('최종 상태입니다').waitFor();
    const { review } = await events(state.jobB);
    assert.equal(review.status, 'rejected');
    assert.equal(review.events.at(-1).decision, 'rejected');
  });

  console.log(`SUMMARY ${results.filter(r => r.ok).length}/${results.length} review steps passed`);
} catch { failed = true; }
finally { await browser.close(); await stack.stop(); }
process.exit(failed ? 1 : 0);
