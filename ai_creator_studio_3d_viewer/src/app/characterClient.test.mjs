import test from 'node:test';
import assert from 'node:assert/strict';
import { identityFromLibraryModel, profileCard, validateProfile, createProfile, MAX_REFS } from './characterClient.mjs';

const MODEL = { name_ko: '샘플 모델 1', attributes: { skin_tone: '3', hair: 'wavy', body_type: 'regular', age_range: '30s', region_style: 'europe' } };

test('a library model becomes an identity with its attributes, nothing invented', () => {
  const id = identityFromLibraryModel(MODEL, '  브랜드 모델 A ');
  assert.deepEqual(id, { name: '브랜드 모델 A', age_range: '30s', hairstyle: 'wavy', body_type: 'regular', skin_tone: 'tone-3', distinguishing_features: ['region_style:europe'] });
  const bare = identityFromLibraryModel({ name_ko: '이름만' });
  assert.deepEqual(bare, { name: '이름만', age_range: 'adult', hairstyle: 'unspecified', body_type: 'unspecified', skin_tone: 'unspecified', distinguishing_features: [] });
  assert.equal(identityFromLibraryModel(MODEL, 'x'.repeat(300)).name.length, 120);
});

test('the profile card shows the attributes in Korean as style labels, and the number of reference images', () => {
  const card = profileCard({ identity: identityFromLibraryModel(MODEL, 'A'), asset_ids: ['a1', 'a2'] });
  assert.equal(card.name, 'A'); assert.equal(card.references, 2);
  for (const part of ['30대', '표준', '웨이브', '피부색 3단계', '지역 느낌 유럽']) assert.ok(card.summary.includes(part), part);
  assert.equal(profileCard({ identity: { name: 'B', age_range: 'adult', hairstyle: 'unspecified', body_type: 'unspecified', skin_tone: 'unspecified' }, asset_ids: [] }).summary, '');
  assert.deepEqual(profileCard(null), { name: '', summary: '', references: 0 });
});

test('a profile needs a name and 1 to 5 distinct reference images', () => {
  assert.equal(validateProfile({ name: 'A', assetIds: ['a'] }), '');
  assert.equal(validateProfile({ name: 'A', assetIds: ['a', 'b', 'c', 'd', 'e'] }), '');
  assert.match(validateProfile({ name: ' ', assetIds: ['a'] }), /이름/);
  assert.match(validateProfile({ name: 'A', assetIds: [] }), /1장 이상/);
  assert.match(validateProfile({ name: 'A', assetIds: ['a', 'b', 'c', 'd', 'e', 'f'] }), /최대 5장/);
  assert.match(validateProfile({ name: 'A', assetIds: ['a', 'a'] }), /두 번/);
  assert.equal(MAX_REFS, 5);
});

test('creating posts identity, no outfits and the reference asset ids to the workspace characters endpoint', async () => {
  let seen;
  globalThis.fetch = async (url, init) => { seen = { url: String(url).replace('http://127.0.0.1:9', ''), method: init.method, body: JSON.parse(init.body) }; return new Response('{}', { status: 201 }); };
  await createProfile('http://127.0.0.1:9', 't', 'ws 1', { identity: { name: 'A' }, assetIds: ['x'] });
  assert.deepEqual(seen, { url: '/v1/workspaces/ws%201/characters', method: 'POST', body: { identity: { name: 'A' }, outfits: [], asset_ids: ['x'] } });
});
