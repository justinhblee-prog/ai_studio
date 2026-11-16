// R-038: 3D Studio (viewing). Models are the workspace's own .glb/.gltf assets; nothing is sent to an external AI service.
import { apiRequest } from './apiClient.mjs';

export const BACKGROUNDS = Object.freeze([
  { value: '#171a21', label: '어두운 스튜디오' }, { value: '#e8eaed', label: '밝은 회색' },
  { value: '#ffffff', label: '흰색' }, { value: '#1e2a3a', label: '짙은 파랑' },
]);
export const MAX_MODEL_BYTES = 50 * 1024 * 1024;

export function validateModelFile(file) {
  if (!file) return '파일을 골라 주세요.';
  if (!/\.(glb|gltf)$/i.test(file.name || '')) return '.glb 또는 .gltf 파일만 올릴 수 있습니다.';
  if (file.size > MAX_MODEL_BYTES) return `파일이 너무 큽니다(최대 ${MAX_MODEL_BYTES / 1024 / 1024}MB).`;
  if (file.size === 0) return '빈 파일입니다.';
  return '';
}

export const currentVersionId = (versions) => (versions?.items ?? []).find((v) => v.is_current)?.version_id ?? null;

// The viewer fetches this with the bearer token (authenticated, immutable version content, never an open address).
export const modelContentUrl = (api, assetId, versionId) =>
  `${String(api || '').trim().replace(/\/+$/, '')}/v1/assets/${encodeURIComponent(assetId)}/versions/${encodeURIComponent(versionId)}/preview-content`;

export const listModels = (api, token, workspaceId) => apiRequest(api, `/v1/assets?workspace_id=${encodeURIComponent(workspaceId)}&kind=model`, { token });
export const listVersions = (api, token, assetId) => apiRequest(api, `/v1/assets/${encodeURIComponent(assetId)}/versions`, { token });

export async function uploadModel(api, token, workspaceId, file) {
  const form = new FormData();
  form.set('workspace_id', workspaceId);
  form.set('file', file);
  const response = await fetch(`${String(api || '').trim().replace(/\/+$/, '')}/v1/assets`, { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: form });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw Object.assign(new Error(typeof body?.detail === 'string' ? body.detail : body?.detail?.message || `업로드 실패 (${response.status})`), { status: response.status });
  }
  return response.json();
}
