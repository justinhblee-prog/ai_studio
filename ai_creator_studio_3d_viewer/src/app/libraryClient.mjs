// R-033: the default asset library from the screen's side. All requests go through apiRequest (bearer token, Korean 429 text).
import { apiRequest } from './apiClient.mjs';

// Screen tabs: 모델 · 의류 · 액세서리 · 배경, each a group of server categories.
export const GROUPS = Object.freeze([
  { key: 'model', label: '모델', categories: ['model'] },
  { key: 'clothes', label: '의류', categories: ['top', 'bottom', 'dress', 'outer'] },
  { key: 'accessory', label: '액세서리', categories: ['bag', 'hat', 'eyewear', 'shoes', 'jewelry', 'headwear', 'belt_scarf'] },
  { key: 'background', label: '배경', categories: ['background'] },
]);
export const CATEGORY_LABELS = Object.freeze({
  model: '모델', top: '상의', bottom: '하의', dress: '원피스', outer: '아우터', bag: '가방', hat: '모자', eyewear: '안경·선글라스',
  shoes: '신발', jewelry: '주얼리', headwear: '머리 덮개', belt_scarf: '벨트·스카프', background: '배경',
});
// Model filters (values are the server's allowed values; labels are only for display, not claims about any real person).
export const MODEL_FILTERS = Object.freeze({
  skin_tone: { label: '피부색', options: [['1', '1단계(밝음)'], ['2', '2단계'], ['3', '3단계'], ['4', '4단계'], ['5', '5단계'], ['6', '6단계(어두움)']] },
  hair: { label: '머리', options: [['straight', '직모'], ['wavy', '웨이브'], ['curly', '곱슬'], ['short', '짧은 머리'], ['covered', '머리 덮개']] },
  body_type: { label: '체형', options: [['slim', '슬림'], ['regular', '표준'], ['plus', '플러스']] },
  age_range: { label: '연령대', options: [['20s', '20대'], ['30s', '30대'], ['40s', '40대'], ['50s', '50대']] },
  region_style: { label: '지역 느낌', options: [['east_asia', '동아시아'], ['southeast_asia', '동남아시아'], ['south_asia', '남아시아'], ['middle_east', '중동'], ['africa', '아프리카'], ['europe', '유럽'], ['latin_america', '라틴아메리카']] },
});
export const AI_LABEL = 'AI 생성 이미지';
export const TEST_MARK = '시험 생성';
export const EMPTY_MESSAGE = '이 조건에 맞는 라이브러리 항목이 없습니다.';
export const LOAD_FAILED_MESSAGE = '라이브러리를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.';
export const IMPORT_LIMIT_MESSAGE = '오늘 라이브러리에서 가져올 수 있는 항목 수에 도달했습니다. 내일 다시 시도해 주세요.';

export const groupOf = (key) => GROUPS.find((g) => g.key === key) ?? GROUPS[0];

// "AI 생성 이미지" is shown for every ai_generated item, no exceptions; sample (placeholder) items also say they are samples.
export function labelsFor(item) {
  const labels = [];
  if (item?.is_ai_generated) labels.push(AI_LABEL);
  if (item?.is_placeholder) labels.push('표시용 샘플');
  return labels;
}

export function buildListQuery({ category, q, attributes = {}, cursor, limit = 24 } = {}) {
  const params = new URLSearchParams();
  if (category) params.set('category', category);
  if (q && q.trim()) params.set('q', q.trim());
  for (const [key, value] of Object.entries(attributes)) if (value && Object.prototype.hasOwnProperty.call(MODEL_FILTERS, key)) params.set(key, value);
  if (cursor) params.set('cursor', cursor);
  params.set('limit', String(limit));
  return params.toString();
}

export const listLibraryItems = (api, token, query) => apiRequest(api, `/v1/library/items?${buildListQuery(query)}`, { token });

// The server returns a relative signed path; an <img> needs the full address of the API.
export async function libraryPreviewSrc(api, token, itemId) {
  const base = String(api || '').trim().replace(/\/+$/, '');
  const signed = await apiRequest(api, `/v1/library/items/${encodeURIComponent(itemId)}/preview-url`, { token });
  if (typeof signed?.url !== 'string' || !signed.url.startsWith('/v1/library/items/')) throw new Error('미리보기 주소를 만들지 못했습니다.');
  return `${base}${signed.url}`;
}

// 429 body: {detail:{code:'LIBRARY_IMPORT_LIMIT', limit, used}} -> Korean text (with the numbers when the server sends them);
// any other error keeps the message apiRequest made.
export async function importLibraryItem(api, token, itemId, workspaceId) {
  try {
    return await apiRequest(api, `/v1/library/items/${encodeURIComponent(itemId)}/import`, { token, method: 'POST', body: { workspace_id: workspaceId } });
  } catch (error) {
    throw importErrorFrom(error);
  }
}

export function importErrorFrom(error) {
  if (error?.code === 'LIBRARY_IMPORT_LIMIT') {
    const { limit, used } = error.detail || {};
    return new Error(Number.isInteger(limit) && Number.isInteger(used) ? `${IMPORT_LIMIT_MESSAGE} (오늘 ${used}/${limit}건)` : IMPORT_LIMIT_MESSAGE);
  }
  if (error?.status === 404) return new Error('이 항목은 더 이상 사용할 수 없습니다. 목록을 새로고침해 주세요.');
  if (error?.status === 403) return new Error('이 작업공간에서 가져오려면 편집자 이상의 권한이 필요합니다.');
  return error instanceof Error ? error : new Error('가져오지 못했습니다. 잠시 후 다시 시도해 주세요.');
}
