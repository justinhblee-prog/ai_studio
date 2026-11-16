import test from 'node:test';
import assert from 'node:assert/strict';
import { STEP_DEFS, newStep, validateSteps, moveStep, summarizeRecords, runPhotoSteps, MAX_STEPS } from './photoStepsClient.mjs';

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
