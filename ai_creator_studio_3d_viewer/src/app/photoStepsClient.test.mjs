import test from 'node:test';
import assert from 'node:assert/strict';
import { STEP_DEFS, newStep, validateSteps, moveStep, summarizeRecords, runPhotoSteps, MAX_STEPS, stepsFromPreset, validatePresetName, savePreset, planBulk, uploadMany, PLANNED_STEPS, MAX_BULK_FILES } from './photoStepsClient.mjs';

test('a new step carries the defaults of its definition; an unknown one is refused', () => {
  assert.deepEqual(newStep('auto_crop'), { op: 'auto_crop', tolerance: 24, margin_pct: 5 });
  assert.deepEqual(newStep('fit_canvas'), { op: 'fit_canvas', width: 1200, height: 1200, color: '#ffffff' });
  assert.throws(() => newStep('sharpen'));
  assert.ok(Object.values(STEP_DEFS).every((d) => /[가-힣]/.test(d.label) && d.params.length));
});

test('validation mirrors the server bounds and says which step is wrong', () => {
  assert.equal(validateSteps([newStep('auto_crop'), newStep('fit_canvas')]), '');
  assert.match(validateSteps([]), /하나 이상/);
  assert.match(validateSteps(Array.from({ length: MAX_STEPS + 1 }, () => newStep('auto_crop'))), /최대 12/);
  assert.match(validateSteps([{ ...newStep('auto_crop'), tolerance: 999 }]), /1번 단계: 배경 허용 오차/);
  assert.match(validateSteps([newStep('auto_crop'), { ...newStep('fit_canvas'), width: 10 }]), /2번 단계: 가로/);
  assert.match(validateSteps([{ ...newStep('solid_background'), color: 'red' }]), /#rrggbb/);
  assert.match(validateSteps([{ ...newStep('auto_crop'), margin_pct: 1.5 }]), /정수/);
});

test('steps can be reordered within bounds without mutating the original list', () => {
  const list = [newStep('auto_crop'), newStep('solid_background'), newStep('fit_canvas')];
  assert.deepEqual(moveStep(list, 2, -1).map((s) => s.op), ['auto_crop', 'fit_canvas', 'solid_background']);
  assert.deepEqual(list.map((s) => s.op), ['auto_crop', 'solid_background', 'fit_canvas']);
  assert.equal(moveStep(list, 0, -1), list); assert.equal(moveStep(list, 2, 1), list);
});

test('the result summary shows each step in Korean with sizes', () => {
  assert.deepEqual(summarizeRecords([{ op: 'auto_crop', size_in: [200, 100], size_out: [80, 60] }]), ['자동 크롭: 200×100 → 80×60']);
  assert.deepEqual(summarizeRecords(null), []);
});

test('running posts the asset id and the steps to the workspace endpoint', async () => {
  let seen;
  globalThis.fetch = async (url, init) => { seen = { url: String(url).replace('http://127.0.0.1:9', ''), body: JSON.parse(init.body) }; return new Response('{}', { status: 201 }); };
  await runPhotoSteps('http://127.0.0.1:9', 't', 'ws 1', 'a1', [newStep('auto_crop')]);
  assert.deepEqual(seen, { url: '/v1/workspaces/ws%201/photo-steps', body: { asset_id: 'a1', steps: [{ op: 'auto_crop', tolerance: 24, margin_pct: 5 }] } });
});

test('applying a preset copies its steps; the saved preset is never changed by later edits', () => {
  const preset = { preset_id: 'p', name: 'A', steps: [newStep('auto_crop')] };
  const copy = stepsFromPreset(preset);
  copy[0].margin_pct = 30;
  assert.equal(preset.steps[0].margin_pct, 5);
  assert.deepEqual(stepsFromPreset(null), []);
});

test('preset names: required, at most 60, unique', () => {
  assert.equal(validatePresetName('봄 시즌', [{ name: '기본' }]), '');
  assert.match(validatePresetName('  '), /입력/);
  assert.match(validatePresetName('x'.repeat(61)), /60자/);
  assert.match(validatePresetName(' 기본 ', [{ name: '기본' }]), /이미 있습니다/);
});

test('saving a preset posts the trimmed name and the steps', async () => {
  let seen;
  globalThis.fetch = async (url, init) => { seen = { url: String(url).replace('http://127.0.0.1:9', ''), body: JSON.parse(init.body) }; return new Response('{}', { status: 201 }); };
  await savePreset('http://127.0.0.1:9', 't', 'ws', '  기본 ', [newStep('auto_crop')]);
  assert.deepEqual(seen, { url: '/v1/workspaces/ws/photo-presets', body: { name: '기본', steps: [{ op: 'auto_crop', tolerance: 24, margin_pct: 5 }] } });
});

test('bulk plan keeps images, lists the rest with a reason, and caps the count', () => {
  const files = [{ name: 'a.PNG' }, { name: 'b.jpeg' }, { name: 'notes.txt' }, { name: 'c.webp' }];
  const plan = planBulk(files);
  assert.deepEqual(plan.accepted.map((f) => f.name), ['a.PNG', 'b.jpeg', 'c.webp']);
  assert.deepEqual(plan.skipped, [{ name: 'notes.txt', reason: 'png·jpg·webp 이미지가 아닙니다.' }]);
  const many = planBulk(Array.from({ length: MAX_BULK_FILES + 2 }, (_, i) => ({ name: `i${i}.png` })));
  assert.equal(many.accepted.length, MAX_BULK_FILES); assert.equal(many.skipped.length, 2); assert.match(many.skipped[0].reason, /최대 20장/);
  assert.deepEqual(planBulk(null), { accepted: [], skipped: [] });
});

test('bulk upload goes one by one, a failure does not stop the rest, and each file is reported', async () => {
  const seen = [];
  const upload = async (api, token, ws, file, declaration) => {
    seen.push([file.name, declaration.rightsConfirmed]);
    if (file.name === 'bad.png') throw Object.assign(new Error('거부됨'), { status: 422 });
    return { asset_id: `id-${file.name}` };
  };
  const result = await uploadMany('x', 't', 'ws', [{ name: 'a.png' }, { name: 'bad.png' }, { name: 'c.png' }], { rightsConfirmed: true, depictsPerson: false, likenessConsent: false }, upload);
  assert.deepEqual(seen, [['a.png', true], ['bad.png', true], ['c.png', true]]);
  assert.deepEqual(result.done.map((d) => d.asset.asset_id), ['id-a.png', 'id-c.png']);
  assert.deepEqual(result.failed, [{ name: 'bad.png', reason: '거부됨', status: 422 }]);
});

test('the default upload sends the workspace, the file and the rights declaration with the token', async () => {
  let seen;
  globalThis.fetch = async (url, init) => { seen = { url: String(url), auth: init.headers.Authorization, rights: init.body.get('rights_confirmed'), ws: init.body.get('workspace_id') }; return new Response('{"asset_id":"a"}', { status: 201 }); };
  const result = await uploadMany('http://127.0.0.1:9/', 't', 'ws-1', [new File([new Uint8Array(3)], 'x.png')], { rightsConfirmed: true, depictsPerson: false, likenessConsent: false });
  assert.deepEqual(seen, { url: 'http://127.0.0.1:9/v1/assets/images', auth: 'Bearer t', rights: 'true', ws: 'ws-1' });
  assert.equal(result.done.length, 1);
});

test('planned steps are listed in Korean', () => { assert.ok(PLANNED_STEPS.length >= 7 && !PLANNED_STEPS.some((n) => /그림자|화이트/.test(n)) && PLANNED_STEPS.every((n) => /[가-힣]/.test(n))); });

test('the new local steps have defaults and bounds that match the server', () => {
  assert.deepEqual(newStep('white_balance'), { op: 'white_balance', strength_pct: 100 });
  assert.deepEqual(newStep('drop_shadow'), { op: 'drop_shadow', offset_x: 0, offset_y: 12, blur: 16, opacity_pct: 40 });
  assert.deepEqual(newStep('gradient_background'), { op: 'gradient_background', top_color: '#ffffff', bottom_color: '#e6e6e6' });
  assert.equal(validateSteps([newStep('drop_shadow'), newStep('white_balance'), newStep('gradient_background')]), '');
  assert.equal(validateSteps([{ ...newStep('drop_shadow'), offset_x: -200 }]), '');
  assert.match(validateSteps([{ ...newStep('drop_shadow'), blur: 101 }]), /1번 단계: 번짐/);
  assert.match(validateSteps([{ ...newStep('drop_shadow'), offset_y: 201 }]), /세로 이동/);
  assert.match(validateSteps([{ ...newStep('gradient_background'), top_color: 'x' }]), /위쪽 색/);
});
