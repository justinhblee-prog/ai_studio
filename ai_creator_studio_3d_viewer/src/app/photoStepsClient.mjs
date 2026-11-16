// R-044 A-3: screen side of the local photo steps. Bounds mirror the server (app/photo_steps.py); the server stays the authority.
import { apiRequest } from './apiClient.mjs';
import { appendRightsDeclaration } from './rightsDeclaration.mjs';

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
  gradient_background: { label: '그라데이션 배경', help: '투명한 부분을 위→아래 두 색의 그라데이션으로 채웁니다.', params: [
    { key: 'top_color', label: '위쪽 색', type: 'color', value: '#ffffff' },
    { key: 'bottom_color', label: '아래쪽 색', type: 'color', value: '#e6e6e6' }] },
  white_balance: { label: '화이트 밸런스', help: '전체 색 기울기를 중립 회색 기준으로 맞춥니다(강도로 원본과 섞음).', params: [
    { key: 'strength_pct', label: '강도(%)', type: 'int', min: 0, max: 100, value: 100 }] },
  drop_shadow: { label: '그림자 넣기', help: '배경이 투명한 이미지에서 물체 아래에 부드러운 그림자를 만듭니다. 그 뒤에 배경 단계를 붙여 주세요.', params: [
    { key: 'offset_x', label: '가로 이동(px)', type: 'int', min: -200, max: 200, value: 0 },
    { key: 'offset_y', label: '세로 이동(px)', type: 'int', min: -200, max: 200, value: 12 },
    { key: 'blur', label: '번짐', type: 'int', min: 0, max: 100, value: 16 },
    { key: 'opacity_pct', label: '진하기(%)', type: 'int', min: 0, max: 100, value: 40 }] },
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

// Several-image import (R-044 A item 2, without ZIP): each file is one ordinary upload with the same rights declaration.
export const MAX_BULK_FILES = 20;
export const IMAGE_NAME = /\.(png|jpe?g|webp)$/i;

// Picks what can be sent; everything else is listed with a Korean reason instead of being dropped silently.
export function planBulk(files) {
  const list = Array.from(files ?? []);
  const skipped = [];
  const accepted = [];
  for (const file of list) {
    if (!IMAGE_NAME.test(file.name || '')) skipped.push({ name: file.name, reason: 'png·jpg·webp 이미지가 아닙니다.' });
    else if (accepted.length >= MAX_BULK_FILES) skipped.push({ name: file.name, reason: `한 번에 최대 ${MAX_BULK_FILES}장까지입니다.` });
    else accepted.push(file);
  }
  return { accepted, skipped };
}

export async function uploadMany(api, token, workspaceId, files, declaration, upload = uploadOne) {
  const done = [];
  const failed = [];
  for (const file of files) {
    try { done.push({ name: file.name, asset: await upload(api, token, workspaceId, file, declaration) }); }
    catch (reason) { failed.push({ name: file.name, reason: reason?.message || '업로드하지 못했습니다.', status: reason?.status }); }
  }
  return { done, failed };
}

async function uploadOne(api, token, workspaceId, file, declaration) {
  const form = new FormData();
  form.set('workspace_id', workspaceId);
  form.set('file', file);
  appendRightsDeclaration(form, declaration);
  const response = await fetch(`${String(api || '').trim().replace(/\/+$/, '')}/v1/assets/images`, { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: form });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw Object.assign(new Error(typeof body?.detail === 'string' ? body.detail : body?.detail?.message || `업로드 실패 (${response.status})`), { status: response.status });
  }
  return response.json();
}

// Steps the photo studio plans but does not have yet; shown (not hidden) as "개발 예정".
export const PLANNED_STEPS = Object.freeze([
  '배경 제거(투명 PNG)', '반사', '형태·로고 보존 확인',
  '주름·먼지·잡티 정리(외부 AI)', '업스케일', '장면 배경 교체(외부 AI)', '색상 변형', '일괄 처리 큐',
]);
