// R-044 A-3 in the browser: local photo steps panel. Real: web bundle, backend, SQLite. Mocked: Supabase Auth.
import assert from 'node:assert/strict';
import { startStack, chromium, mockSupabase, loginThroughUi, gotoPage, makeRunner, apiCall, makePng, USERS } from './harness.mjs';

const stack = await startStack();
const browser = await chromium.launch();
let failed = false;
try {
  const context = await browser.newContext(); await mockSupabase(context, USERS.owner);
  const page = await context.newPage();
  const { run, results } = makeRunner(page, stack);
  const state = {};
  const panel = () => page.locator('section[aria-label="사진 단계 편집"]');
  const images = async () => (await apiCall(stack, USERS.owner.token, `/v1/assets?workspace_id=${state.workspace}&kind=image`)).body.items;

  await run('the panel opens on the photo screen; with no image it says so and cannot run', async () => {
    await loginThroughUi(page, stack.webUrl, USERS.owner);
    state.workspace = await page.locator('.workspace-select').inputValue();
    await gotoPage(page, '포토 스튜디오');
    await panel().getByRole('option', { name: '이미지가 없습니다' }).waitFor({ state: 'attached', timeout: 10000 });
    assert.equal(await panel().getByRole('button', { name: /실행해서/ }).isDisabled(), true);
  });

  await run('steps can be added, reordered and removed; out-of-range values block the run with a Korean reason', async () => {
    const f = new FormData(); f.set('workspace_id', state.workspace); f.set('rights_confirmed', 'true');
    f.set('file', new Blob([makePng(60, 40, [200, 40, 40])], { type: 'image/png' }), 'shoe.png');
    const up = await fetch(`${stack.apiUrl}/v1/assets/images`, { method: 'POST', headers: { Authorization: `Bearer ${USERS.owner.token}` }, body: f });
    assert.equal(up.status, 201, await up.text());
    await page.reload(); await page.locator('.workspace-select').waitFor({ timeout: 20000 });
    await gotoPage(page, '포토 스튜디오');
    await panel().getByLabel('편집할 이미지').selectOption({ label: 'shoe.png' });
    await panel().getByRole('button', { name: /단색 배경/ }).click();
    await panel().getByRole('button', { name: /캔버스 맞춤/ }).click();
    const items = panel().locator('ol[aria-label="적용할 단계"] > li');
    assert.equal(await items.count(), 2);
    await panel().getByRole('button', { name: '2번 단계 위로' }).click();
    assert.match(await items.first().innerText(), /캔버스 맞춤/);
    await items.first().getByLabel('가로(px)').fill('5');
    await panel().getByText(/1번 단계: 가로/).waitFor();
    assert.equal(await panel().getByRole('button', { name: /실행해서/ }).isDisabled(), true);
    await items.first().getByLabel('가로(px)').fill('100');
    await items.first().getByLabel('세로(px)').fill('100');
    assert.equal(await panel().getByRole('button', { name: /실행해서/ }).isDisabled(), false);
    await panel().getByRole('button', { name: '2번 단계 삭제' }).click();
    assert.equal(await items.count(), 1);
  });

  await run('running saves a NEW image asset of the chosen size, keeps the original, and shows the result', async () => {
    const before = (await images()).length;
    await panel().getByRole('button', { name: /실행해서/ }).click();
    await panel().getByRole('status', { name: '단계 실행 결과' }).waitFor({ timeout: 15000 });
    const text = await panel().getByRole('status', { name: '단계 실행 결과' }).innerText();
    assert.ok(text.includes('shoe-edited.png') && text.includes('60×40 → 100×100'), text);
    const after = await images();
    assert.equal(after.length, before + 1); assert.ok(after.some(a => a.original_filename === 'shoe.png'), 'original kept');
    await page.waitForFunction(() => { const i = document.querySelector('img[alt="편집 결과 미리보기"]'); return i && i.naturalWidth === 100; }, null, { timeout: 10000 });
  });

  await run('a viewer-less failure is shown in Korean: the same run against a deleted source reports an error and stores nothing', async () => {
    const [shoe] = (await images()).filter(a => a.original_filename === 'shoe.png');
    assert.equal((await apiCall(stack, USERS.owner.token, `/v1/assets/${shoe.asset_id}`, { method: 'DELETE' })).status, 204);
    const before = (await images()).length;
    await panel().getByRole('button', { name: /실행해서/ }).click();
    await panel().locator('[role=alert]').first().waitFor({ timeout: 10000 });
    assert.equal((await images()).length, before);
  });

  console.log(`SUMMARY ${results.filter(r => r.ok).length}/${results.length} photo-steps steps passed`);
} catch { failed = true; }
finally { await browser.close(); await stack.stop(); }
process.exit(failed ? 1 : 0);
