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

  await run('before/after: the original (60 wide) and the result (100 wide) are shown side by side', async () => {
    const compare = panel().getByRole('group', { name: '전후 비교' });
    await page.waitForFunction(() => { const i = document.querySelector('img[alt="편집 전 원본"]'); return i && i.naturalWidth === 60; }, null, { timeout: 10000 });
    assert.ok(await compare.getByText('전(원본)').isVisible() && await compare.getByText('후(결과)').isVisible());
  });

  await run('the before/after slider reveals the result from the left as it is moved', async () => {
    const range = panel().getByRole('slider', { name: '전후 비교 슬라이더' });
    await range.waitFor({ timeout: 10000 });
    const after = panel().getByAltText('슬라이더 결과');
    assert.equal(await after.getAttribute('data-clip'), 'inset(0 50% 0 0)', 'starts in the middle');
    await range.fill('30');
    assert.equal(await after.getAttribute('data-clip'), 'inset(0 70% 0 0)');
    assert.match(await after.evaluate(el => getComputedStyle(el).clipPath), /inset\(.*70%/);
    await range.fill('100'); assert.equal(await after.getAttribute('data-clip'), 'inset(0 0% 0 0)');
    await range.fill('0'); assert.equal(await after.getAttribute('data-clip'), 'inset(0 100% 0 0)');
  });

  await run('a preset can be saved from the current steps, applied later, and deleted; names are unique', async () => {
    const items = panel().locator('ol[aria-label="적용할 단계"] > li');
    const save = panel().getByRole('button', { name: '현재 단계를 프리셋으로 저장' });
    assert.equal(await save.isDisabled(), true, 'no name yet');
    await panel().getByLabel('프리셋 이름').fill('브랜드 기본');
    await save.click();
    await panel().getByText('"브랜드 기본" 프리셋을 저장했습니다.').waitFor({ timeout: 10000 });
    const saved = (await apiCall(stack, USERS.owner.token, `/v1/workspaces/${state.workspace}/photo-presets`)).body.items;
    assert.equal(saved.length, 1); assert.equal(saved[0].steps[0].op, 'fit_canvas'); assert.equal(saved[0].steps[0].width, 100);
    await panel().getByLabel('프리셋 이름').fill('브랜드 기본');
    assert.equal(await save.isDisabled(), true, 'same name is refused on the screen');
    await panel().getByRole('button', { name: '1번 단계 삭제' }).click();
    assert.equal(await items.count(), 0);
    await panel().getByLabel('저장된 프리셋').selectOption({ label: '브랜드 기본' });
    assert.equal(await items.count(), 1);
    assert.equal(await items.first().getByLabel('가로(px)').inputValue(), '100');
    await panel().getByRole('button', { name: '브랜드 기본 프리셋 삭제' }).click();
    await page.waitForFunction(() => !document.querySelector('ul[aria-label="프리셋 목록"]'), null, { timeout: 10000 });
    assert.equal((await apiCall(stack, USERS.owner.token, `/v1/workspaces/${state.workspace}/photo-presets`)).body.items.length, 0);
    await panel().getByRole('button', { name: /캔버스 맞춤/ }).click();   // leave one step for the next scenario
  });

  await run('several images at once: rights must be ticked, non-images are listed with a reason, the rest are stored', async () => {
    const before = (await images()).length;
    const set = () => panel().getByLabel('이미지 여러 장 가져오기');
    const png = (name, c) => ({ name, mimeType: 'image/png', buffer: makePng(20, 20, c) });
    await set().setInputFiles([png('one.png', [10, 20, 30])]);
    await panel().locator('[role=alert]').filter({ hasText: /권리 확인/ }).waitFor({ timeout: 10000 });
    assert.equal((await images()).length, before, 'nothing stored without the rights tick');
    await panel().getByRole('checkbox', { name: /사용할 권리가 있음/ }).check();
    await set().setInputFiles([png('one.png', [10, 20, 30]), png('two.png', [30, 20, 10]), { name: 'notes.txt', mimeType: 'text/plain', buffer: Buffer.from('x') }]);
    const result = panel().getByRole('status', { name: '가져오기 결과' });
    await result.getByText('2장을 가져왔습니다.').waitFor({ timeout: 15000 });
    assert.ok((await result.innerText()).includes('notes.txt'), 'the skipped file is named');
    assert.equal((await images()).length, before + 2);
    const names = (await images()).map(a => a.original_filename);
    assert.ok(names.includes('one.png') && names.includes('two.png'));
  });

  await run('steps that do not exist yet are listed as "개발 예정", not hidden', async () => {
    const planned = panel().getByRole('region', { name: '개발 예정 단계' });
    for (const name of ['배경 제거', '반사', '업스케일']) assert.ok((await planned.innerText()).includes(name), name);
    assert.ok((await planned.locator('li').count()) >= 7);
    for (const name of ['그라데이션 배경', '화이트 밸런스', '그림자 넣기']) assert.equal(await panel().getByRole('button', { name: new RegExp(name) }).count(), 1, `${name} is a real step now`);
  });

  await run('the same run against a deleted source reports an error in Korean and stores nothing', async () => {
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
