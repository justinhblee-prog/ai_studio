import test from 'node:test';
import assert from 'node:assert/strict';
import { GROUPS, CATEGORY_LABELS, MODEL_FILTERS, AI_LABEL, labelsFor, buildListQuery, listLibraryItems, libraryPreviewSrc, importLibraryItem, IMPORT_LIMIT_MESSAGE } from './libraryClient.mjs';

const API = 'http://127.0.0.1:9';
function fakeFetch(handler) {
  const calls = [];
  globalThis.fetch = async (url, init = {}) => {
    const call = { url: String(url).replace(API, ''), method: init.method || 'GET', body: init.body ? JSON.parse(init.body) : undefined, headers: init.headers };
    calls.push(call);
    const { status = 200, body = {} } = handler(call);
    return new Response(JSON.stringify(body), { status });
  };
  return calls;
}

test('the four tabs cover all 13 server categories exactly once and every category has a Korean label', () => {
  const all = GROUPS.flatMap((g) => g.categories);
  assert.deepEqual(GROUPS.map((g) => g.label), ['모델', '의류', '액세서리', '배경']);
  assert.equal(all.length, 13); assert.equal(new Set(all).size, 13);
  for (const c of all) assert.match(CATEGORY_LABELS[c], /[가-힣]/, c);
});

test('model filters offer exactly the values the server allows', () => {
  assert.deepEqual(Object.keys(MODEL_FILTERS), ['skin_tone', 'hair', 'body_type', 'age_range', 'region_style']);
  assert.deepEqual(MODEL_FILTERS.skin_tone.options.map(([v]) => v), ['1', '2', '3', '4', '5', '6']);
  assert.deepEqual(MODEL_FILTERS.hair.options.map(([v]) => v), ['straight', 'wavy', 'curly', 'short', 'covered']);
  assert.deepEqual(MODEL_FILTERS.region_style.options.length, 7);
});

test('every AI generated item carries the "AI 생성 이미지" label; others do not; samples say so', () => {
  assert.deepEqual(labelsFor({ is_ai_generated: true, is_placeholder: false }), [AI_LABEL]);
  assert.deepEqual(labelsFor({ is_ai_generated: false, is_placeholder: false }), []);
  assert.deepEqual(labelsFor({ is_ai_generated: true, is_placeholder: true }), [AI_LABEL, '표시용 샘플']);
  assert.deepEqual(labelsFor(undefined), []);
  assert.equal(AI_LABEL, 'AI 생성 이미지');
});

test('the list query carries only known filters, trims the search and the paging cursor', () => {
  assert.equal(buildListQuery({ category: 'model', q: '  여성 ', attributes: { hair: 'wavy', skin_tone: '', evil: 'x' }, cursor: 'model-05' }),
    'category=model&q=%EC%97%AC%EC%84%B1&hair=wavy&cursor=model-05&limit=24');
  assert.equal(buildListQuery(), 'limit=24');
  const calls = fakeFetch(() => ({ body: { items: [], next_cursor: null } }));
  return listLibraryItems(API, 'tok', { category: 'top' }).then((r) => {
    assert.deepEqual(r, { items: [], next_cursor: null });
    assert.equal(calls[0].url, '/v1/library/items?category=top&limit=24');
    assert.equal(calls[0].headers.Authorization, 'Bearer tok');
  });
});

test('the preview address gets the API address in front; anything outside the library path is refused', async () => {
  fakeFetch(() => ({ body: { url: '/v1/library/items/top-01/versions/1/preview?expires=1&signature=s', expires_at: 1 } }));
  assert.equal(await libraryPreviewSrc(`${API}/`, 'tok', 'top-01'), `${API}/v1/library/items/top-01/versions/1/preview?expires=1&signature=s`);
  fakeFetch(() => ({ body: { url: 'https://evil.example/x.png' } }));
  await assert.rejects(() => libraryPreviewSrc(API, 'tok', 'top-01'), /미리보기 주소/);
});

test('import posts the workspace id and the 429 limit becomes Korean text with its numbers', async () => {
  const calls = fakeFetch((c) => (c.body.workspace_id === 'ws-full'
    ? { status: 429, body: { detail: { code: 'LIBRARY_IMPORT_LIMIT', message: 'English internal', limit: 200, used: 200 } } }
    : { status: 201, body: { asset_id: 'ast_1', original_filename: 'top-01.png' } }));
  assert.equal((await importLibraryItem(API, 'tok', 'top-01', 'ws-1')).asset_id, 'ast_1');
  assert.equal(calls[0].url, '/v1/library/items/top-01/import'); assert.equal(calls[0].method, 'POST');
  await assert.rejects(() => importLibraryItem(API, 'tok', 'top-01', 'ws-full'), (e) => e.message === `${IMPORT_LIMIT_MESSAGE} (오늘 200/200건)` && !/English/.test(e.message));
  fakeFetch(() => ({ status: 404, body: { detail: 'Library item not found' } }));
  await assert.rejects(() => importLibraryItem(API, 'tok', 'gone', 'ws-1'), /더 이상 사용할 수 없습니다/);
  fakeFetch(() => ({ status: 403, body: { detail: 'Insufficient workspace role' } }));
  await assert.rejects(() => importLibraryItem(API, 'tok', 'top-01', 'ws-1'), /편집자 이상/);
});
