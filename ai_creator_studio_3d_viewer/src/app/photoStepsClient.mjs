// R-044 A-3: screen side of the local photo steps. Bounds mirror the server (app/photo_steps.py); the server stays the authority.
import { apiRequest } from './apiClient.mjs';

export const MAX_STEPS = 12;
export const STEP_DEFS = Object.freeze({
  auto_crop: { label: '자동 크롭', help: '물체 둘레의 빈 배경을 잘라냅니다.', params: [
    { key: 'tolerance', label: '배경 허용 오차', type: 'int', min: 0, max: 128, value: 24 },
    { key: 'margin_pct', label: '여백(%)', type: 'int', min: 0, max: 40, value: 5 }] },
  solid_background: { label: '단색 배경', help: '투명한 부분을 한 가지 색으로 채웁니다.', params: [
    { key: 'color', label: '배경색', type: 'color', value: '#ffffff' }] },
  fit_canvas: { label: '캔버스 맞춤', help: '자르지 않고 비율을 지킨 채 정해진 크기 캔버스 가운데에 놓습니다.', params: [
    { key: 'width', label: '가로(px)', type: 'int', min: 16, max: 8192, value: 1200 },
    { key: 'height', label: '세로(px)', type: 'int', min: 16, max: 8192, value: 1200 },
    { key: 'color', label: '여백색', type: 'color', value: '#ffffff' }] },
});

export function newStep(op) {
  const def = STEP_DEFS[op];
  if (!def) throw new Error('unknown step');
  return Object.fromEntries([['op', op], ...def.params.map((p) => [p.key, p.value])]);
}

// Korean error text for the first problem, or '' when the list may be sent.
export function validateSteps(steps) {
  if (!steps?.length) return '단계를 하나 이상 추가해 주세요.';
  if (steps.length > MAX_STEPS) return `단계는 최대 ${MAX_STEPS}개입니다.`;
  for (const [i, step] of steps.entries()) {
    for (const p of STEP_DEFS[step.op].params) {
      const v = step[p.key];
      if (p.type === 'int' && !(Number.isInteger(v) && v >= p.min && v <= p.max)) return `${i + 1}번 단계: ${p.label}은(는) ${p.min}~${p.max} 사이 정수여야 합니다.`;
      if (p.type === 'color' && !/^#[0-9a-fA-F]{6}$/.test(v)) return `${i + 1}번 단계: ${p.label}은(는) #rrggbb 형식이어야 합니다.`;
    }
  }
  return '';
}

export const moveStep = (steps, index, delta) => {
  const target = index + delta;
  if (target < 0 || target >= steps.length) return steps;
  const copy = [...steps];
  [copy[index], copy[target]] = [copy[target], copy[index]];
  return copy;
};

export const summarizeRecords = (records) => (records ?? []).map((r) => `${STEP_DEFS[r.op]?.label ?? r.op}: ${r.size_in.join('×')} → ${r.size_out.join('×')}`);

export const runPhotoSteps = (api, token, workspaceId, assetId, steps) =>
  apiRequest(api, `/v1/workspaces/${encodeURIComponent(workspaceId)}/photo-steps`, { token, method: 'POST', body: { asset_id: assetId, steps } });

// Brand presets (R-044 A item 19): named step lists saved per workspace.
const presetBase = (workspaceId) => `/v1/workspaces/${encodeURIComponent(workspaceId)}/photo-presets`;
export const listPresets = (api, token, workspaceId) => apiRequest(api, presetBase(workspaceId), { token });
export const savePreset = (api, token, workspaceId, name, steps) => apiRequest(api, presetBase(workspaceId), { token, method: 'POST', body: { name: String(name).trim(), steps } });
export const deletePreset = (api, token, workspaceId, presetId) => apiRequest(api, `${presetBase(workspaceId)}/${encodeURIComponent(presetId)}`, { token, method: 'DELETE' });

// Applying a preset replaces the list with copies (editing the list afterwards never changes the saved preset).
export const stepsFromPreset = (preset) => (preset?.steps ?? []).map((step) => ({ ...step }));

export function validatePresetName(name, existing = []) {
  const n = String(name ?? '').trim();
  if (!n) return '프리셋 이름을 입력해 주세요.';
  if (n.length > 60) return '프리셋 이름은 60자까지입니다.';
  if (existing.some((p) => p.name === n)) return '같은 이름의 프리셋이 이미 있습니다.';
  return '';
}
