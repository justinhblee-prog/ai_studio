// L-07 in the browser: provider job outputs are labelled as AI generated (or not), with the generator shown.
// Real: web bundle, backend, SQLite, the asset-link worker. Mocked: Supabase Auth. The finished job output is SEEDED (the mock
// provider never produces an image), so the real provider path is not exercised.
import assert from 'node:assert/strict';
import { startStack, chromium, mockSupabase, loginThroughUi, gotoPage, makeRunner, apiCall, seedFinishedJobOutput, sqliteExec, USERS } from './harness.mjs';

const stack = await startStack();
const browser = await chromium.launch();
let failed = false;
try {
  const context = await browser.newContext(); await mockSupabase(context, USERS.owner);
  const page = await context.newPage();
  const { run, results } = makeRunner(page, stack);
  const state = {};
  const openReview = async () => {
    await page.getByRole('button', { name: /설정/ }).click();
    await page.locator('section.settings label', { hasText: '결과 검수 Job ID' }).locator('input').fill(state.jobId);
    await page.getByRole('button', { name: /설정/ }).click();
    await gotoPage(page, '결과물 검수');
    await page.locator('article.acs-output-review-item').first().waitFor({ timeout: 15000 });
  };
  const label = async () => ({ kind: await page.locator('.acs-ai-label').first().getAttribute('data-ai-disclosure'), text: (await page.locator('.acs-ai-label').first().innerText()).trim() });

  await run('a finished mock-provider job with a linked output is reviewable in the UI', async () => {
    await loginThroughUi(page, stack.webUrl, USERS.owner);
    state.workspace = await page.locator('.workspace-select').inputValue();
    const created = await apiCall(stack, USERS.owner.token, '/v1/generation-jobs', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workspace_id: state.workspace, model_image_url: 'https://example.com/m.jpg', garment_image_url: 'https://example.com/g.jpg' }) });
    assert.equal(created.status, 202); state.jobId = created.body.job_id;
    seedFinishedJobOutput(stack, state.jobId);  // the mock provider never finishes a job by itself
    const job = await apiCall(stack, USERS.owner.token, `/v1/generation-jobs/${state.jobId}`);
    assert.equal(job.body.status, 'succeeded');
    await openReview();
  });

  await run('mock provider output: labelled "AI 미사용 출력" (API and UI agree)', async () => {
    const listing = (await apiCall(stack, USERS.owner.token, `/v1/generation-jobs/${state.jobId}/outputs`)).body.data[0];
    assert.equal(listing.is_ai_generated, false); assert.equal(listing.provider, 'mock');
    assert.deepEqual(await label(), { kind: 'non-ai', text: 'AI 미사용 출력' });
  });

  await run('a real provider output: labelled "AI 생성물" with the provider and model', async () => {
    sqliteExec(stack, 'UPDATE generation_jobs SET provider=?, model=? WHERE job_id=?', ['fashn', 'tryon-v1.6', state.jobId]);
    await page.reload();
    await page.locator('.workspace-select').waitFor({ timeout: 20000 });
    await openReview();
    const listing = (await apiCall(stack, USERS.owner.token, `/v1/generation-jobs/${state.jobId}/outputs`)).body.data[0];
    assert.equal(listing.is_ai_generated, true);
    assert.deepEqual(await label(), { kind: 'ai', text: 'AI 생성물 · fashn / tryon-v1.6' });
  });

  await run('the internal manifest of an AI generated output says so', async () => {
    const outputId = (await apiCall(stack, USERS.owner.token, `/v1/generation-jobs/${state.jobId}/outputs`)).body.data[0].id;
    const approve = await apiCall(stack, USERS.owner.token, `/v1/generation-jobs/${state.jobId}/outputs/${outputId}/review/approve`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ comment: 'ok' }) });
    assert.equal(approve.status, 200, JSON.stringify(approve.body));
    const exported = await apiCall(stack, USERS.owner.token, `/v1/generation-jobs/${state.jobId}/outputs/export-manifest`, { method: 'POST' });
    assert.equal(exported.status, 200);
    assert.equal(exported.body.manifest.is_ai_generated, true);
    assert.deepEqual(exported.body.manifest.outputs.map(o => o.is_ai_generated), [true]);
  });

  console.log(`SUMMARY ${results.filter(r => r.ok).length}/${results.length} disclosure steps passed`);
} catch (error) { if (!(globalThis.__reported)) console.log('ERROR ' + (error && error.stack || error).toString().slice(0, 800)); failed = true; }
finally { await browser.close(); await stack.stop(); }
process.exit(failed ? 1 : 0);
