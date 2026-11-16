import test from 'node:test';
import assert from 'node:assert/strict';
import { aiDisclosureLabel } from './aiDisclosure.mjs';

test('AI generated outputs are labelled, with the generator when known', () => {
  assert.deepEqual(aiDisclosureLabel(true, 'fashn', 'tryon-v1.6'), { kind: 'ai', text: 'AI 생성물 · fashn / tryon-v1.6' });
  assert.deepEqual(aiDisclosureLabel(true, 'fashn', null), { kind: 'ai', text: 'AI 생성물 · fashn' });
  assert.deepEqual(aiDisclosureLabel(true), { kind: 'ai', text: 'AI 생성물' });
});

test('only an explicit false is called AI-free', () => {
  assert.equal(aiDisclosureLabel(false, 'mock', 'mock-tryon').kind, 'non-ai');
  assert.equal(aiDisclosureLabel(false).text, 'AI 미사용 출력');
});

test('a missing value is unknown, never silently treated as AI-free', () => {
  for (const value of [undefined, null]) assert.equal(aiDisclosureLabel(value, 'fashn', 'x').kind, 'unknown');
  assert.equal(aiDisclosureLabel(undefined).text, 'AI 생성 여부 미확인');
});

test('the wording follows where the inputs came from: own photos = AI edited, library AI = AI generated, unknown = the careful default', () => {
  assert.equal(aiDisclosureLabel(true, 'fashn', 'v1', 'uploaded').text, 'AI 편집 이미지 · fashn / v1');
  assert.equal(aiDisclosureLabel(true, 'fashn', 'v1', 'platform_library_ai').text, 'AI 생성 이미지 · fashn / v1');
  assert.equal(aiDisclosureLabel(true, 'fashn', 'v1', 'unknown').text, 'AI 생성물 · fashn / v1');
  assert.equal(aiDisclosureLabel(true, 'fashn', 'v1').text, 'AI 생성물 · fashn / v1');
  assert.equal(aiDisclosureLabel(true, null, null, 'uploaded').text, 'AI 편집 이미지');
  // inputs never turn a non-AI or unknown output into an AI one, or the other way round
  assert.deepEqual(aiDisclosureLabel(false, 'mock', null, 'uploaded'), { kind: 'non-ai', text: 'AI 미사용 출력' });
  assert.equal(aiDisclosureLabel(undefined, null, null, 'uploaded').kind, 'unknown');
});
