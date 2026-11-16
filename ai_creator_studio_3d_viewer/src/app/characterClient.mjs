// R-039: "brand model profiles" on top of the existing Character API: a name, 1-5 reference images, the model attributes, optionally copied
// from a library model. Attributes are filter labels (skin tone step, hair, body type, age range, region style), not claims about a real person.
import { apiRequest } from './apiClient.mjs';
import { MODEL_FILTERS } from './libraryClient.mjs';

export const MIN_REFS = 1;
export const MAX_REFS = 5;

const labelOf = (key, value) => MODEL_FILTERS[key]?.options.find(([v]) => v === value)?.[1] ?? value;

// Library model -> Character identity. Unknown values stay "unspecified"; nothing is invented.
export function identityFromLibraryModel(item, name) {
  const a = item?.attributes ?? {};
  return {
    name: String(name || item?.name_ko || '').trim().slice(0, 120),
    age_range: a.age_range || 'adult', hairstyle: a.hair || 'unspecified', body_type: a.body_type || 'unspecified',
    skin_tone: a.skin_tone ? `tone-${a.skin_tone}` : 'unspecified',
    distinguishing_features: a.region_style ? [`region_style:${a.region_style}`] : [],
  };
}

export function profileCard(character) {
  const id = character?.identity ?? {};
  const skin = /^tone-(\d)$/.exec(id.skin_tone || '');
  const parts = [
    id.age_range && id.age_range !== 'adult' ? labelOf('age_range', id.age_range) : null,
    id.body_type && id.body_type !== 'unspecified' ? labelOf('body_type', id.body_type) : null,
    id.hairstyle && id.hairstyle !== 'unspecified' ? labelOf('hair', id.hairstyle) : null,
    skin ? `피부색 ${skin[1]}단계` : null,
    ...(id.distinguishing_features ?? []).filter((f) => f.startsWith('region_style:')).map((f) => `지역 느낌 ${labelOf('region_style', f.slice(13))}`),
  ].filter(Boolean);
  return { name: id.name ?? '', summary: parts.join(' · '), references: (character?.asset_ids ?? []).length };
}

// Returns an error text (Korean) or '' when the profile may be saved.
export function validateProfile({ name, assetIds }) {
  if (!String(name || '').trim()) return '프로필 이름을 입력해 주세요.';
  const n = (assetIds ?? []).length;
  if (n < MIN_REFS) return `기준 이미지를 ${MIN_REFS}장 이상 골라 주세요.`;
  if (n > MAX_REFS) return `기준 이미지는 최대 ${MAX_REFS}장까지입니다.`;
  if (new Set(assetIds).size !== n) return '같은 이미지를 두 번 고를 수 없습니다.';
  return '';
}

const base = (workspaceId) => `/v1/workspaces/${encodeURIComponent(workspaceId)}/characters`;
export const listProfiles = (api, token, workspaceId) => apiRequest(api, base(workspaceId), { token });
export const createProfile = (api, token, workspaceId, { identity, assetIds }) =>
  apiRequest(api, base(workspaceId), { token, method: 'POST', body: { identity, outfits: [], asset_ids: assetIds } });
export const deleteProfile = (api, token, workspaceId, characterId) =>
  apiRequest(api, `${base(workspaceId)}/${encodeURIComponent(characterId)}`, { token, method: 'DELETE' });
export const loadFeatures = (api, token) => apiRequest(api, '/v1/features', { token });
