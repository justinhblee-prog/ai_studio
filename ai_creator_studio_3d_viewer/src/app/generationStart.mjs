// R-026: starting a virtual try-on generation job from the screen (design option 1: URLs built by the client).
// ALL provider-facing calls live in startGeneration() so the planned server-side signing (option 2: the job takes
// asset ids) only has to replace this one function. Mock provider only: nothing here selects or configures a provider.
import { apiRequest } from './apiClient.mjs';

export const CATEGORY_OPTIONS = [['auto', '자동'], ['tops', '상의'], ['bottoms', '하의'], ['one-pieces', '원피스'], ['outerwear', '아우터']];
export const MODE_OPTIONS = [['performance', '속도 우선'], ['balanced', '균형'], ['quality', '품질 우선']];
export const RESOLUTION_OPTIONS = [['1k', '1k'], ['2k', '2k'], ['4k', '4k']];
export const FORMAT_OPTIONS = [['png', 'PNG'], ['jpeg', 'JPEG']];
export const NOT_READY_MESSAGE = '생성 준비 중입니다. 서비스의 공개 주소가 아직 설정되지 않아 지금은 생성을 시작할 수 없습니다.';

// The provider must be able to reach the image URLs, so only an https address counts; anything else means "not ready".
export function resolvePublicBase(value) {
  const text = String(value ?? '').trim().replace(/\/+$/, '');
  if (!text) return '';
  try {
    const url = new URL(text);
    return url.protocol === 'https:' && !url.search && !url.hash ? text : '';
  } catch { return ''; }
}

export const generationReady = (publicBase) => Boolean(resolvePublicBase(publicBase));

// Prepends the public address to the server's relative signed path; refuses anything that is not an asset preview path.
export function absolutizePreviewUrl(publicBase, relative) {
  const base = resolvePublicBase(publicBase);
  if (!base) throw new Error(NOT_READY_MESSAGE);
  if (typeof relative !== 'string' || !/^\/v1\/assets\/[^?#]+\/preview\?/.test(relative)) throw new Error('이미지 주소를 만들지 못했습니다.');
  return `${base}${relative}`;
}

export function buildGenerationRequest({ workspaceId, modelUrl, garmentUrl, category = 'auto', mode = 'balanced', resolution = '2k', outputFormat = 'png', prompt = '' }) {
  const body = { workspace_id: workspaceId, model_image_url: modelUrl, garment_image_url: garmentUrl, category, mode, resolution, output_format: outputFormat };
  const text = String(prompt ?? '').trim();
  if (text) body.prompt = text.slice(0, 500);
  return body;
}

async function pinnedPreviewUrl(api, token, publicBase, assetId) {
  const versions = await apiRequest(api, `/v1/assets/${encodeURIComponent(assetId)}/versions`, { token });
  const current = (versions?.items || []).find((v) => v.is_current);
  if (!current) throw new Error('이미지의 현재 버전을 찾지 못했습니다.');
  const signed = await apiRequest(api, `/v1/assets/${encodeURIComponent(assetId)}/versions/${encodeURIComponent(current.version_id)}/preview-url`, { token, method: 'POST' });
  return absolutizePreviewUrl(publicBase, signed?.url);
}

// The single place that talks to the generation API. Throws before any network call when the public address is unset.
export async function startGeneration({ api, token, publicBase, workspaceId, modelAssetId, garmentAssetId, options = {}, idempotencyKey }) {
  if (!generationReady(publicBase)) throw new Error(NOT_READY_MESSAGE);
  if (!modelAssetId || !garmentAssetId) throw new Error('모델 사진과 의류 사진을 모두 선택해 주세요.');
  const modelUrl = await pinnedPreviewUrl(api, token, publicBase, modelAssetId);
  const garmentUrl = await pinnedPreviewUrl(api, token, publicBase, garmentAssetId);
  const body = buildGenerationRequest({ workspaceId, modelUrl, garmentUrl, ...options });
  return apiRequest(api, '/v1/generation-jobs', { token, method: 'POST', body, headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined });
}

export const loadGenerationJob = (api, token, jobId) => apiRequest(api, `/v1/generation-jobs/${encodeURIComponent(jobId)}`, { token });
