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
