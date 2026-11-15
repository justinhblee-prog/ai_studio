import test from 'node:test';
import assert from 'node:assert/strict';
import { MESSAGES, messageForStatus, errorText, responseErrorText, isNetworkError, authErrorText, AUTH_FALLBACK } from './errorMessages.mjs';
import { apiRequest } from './apiClient.mjs';

const API = 'http://127.0.0.1:9';
const fakeFetch = (status, body) => { globalThis.fetch = async () => new Response(JSON.stringify(body ?? {}), { status }); };
const ENGLISH = /[A-Za-z]{4,}/;

test('the four cases of the request: 401, 429, 503 and a dropped connection are Korean and never show the English text', async () => {
  fakeFetch(401, { detail: 'Invalid bearer token' });
  const e401 = errorText(await apiRequest(API, '/v1/x', { token: 't' }).catch((e) => e), '실패');
  fakeFetch(429, { detail: { code: 'SOMETHING_ELSE', message: 'Too Many Requests' } });
  const e429 = errorText(await apiRequest(API, '/v1/x').catch((e) => e), '실패');
  fakeFetch(503, { detail: 'Service Unavailable' });
  const e503 = errorText(await apiRequest(API, '/v1/x').catch((e) => e), '실패');
  globalThis.fetch = async () => { throw new TypeError('Failed to fetch'); };
  const eNet = errorText(await apiRequest(API, '/v1/x').catch((e) => e), '실패');
  assert.deepEqual([e401, e429, e503, eNet], [MESSAGES.unauthorized, MESSAGES.tooMany, MESSAGES.server, MESSAGES.network]);
  for (const text of [e401, e429, e503, eNet]) assert.ok(!ENGLISH.test(text), text);
});

test('a message that is already Korean passes through, also from the server', () => {
  assert.equal(errorText(new Error('이미지 목록을 불러오지 못했습니다.'), '실패'), '이미지 목록을 불러오지 못했습니다.');
  assert.equal(messageForStatus(422, '이미지에 사람이 나오면 동의 확인이 필요합니다.'), '이미지에 사람이 나오면 동의 확인이 필요합니다.');
  // the app's own generic status text is not a real explanation: the status decides
  assert.equal(messageForStatus(503, '요청 실패 (503)'), MESSAGES.server);
  assert.equal(errorText(Object.assign(new Error('API 요청 실패 (503)'), { status: 503 }), 'x'), MESSAGES.server);
});

test('status mapping covers the usual cases and never leaks a raw code or English word', () => {
  const table = { 400: 'invalid', 401: 'unauthorized', 403: 'forbidden', 404: 'notFound', 409: 'conflict', 413: 'tooLarge', 422: 'invalid', 429: 'tooMany', 500: 'server', 502: 'server', 503: 'server', 504: 'server' };
  for (const [status, key] of Object.entries(table)) assert.equal(messageForStatus(Number(status), 'English detail'), MESSAGES[key], status);
  assert.match(messageForStatus(418, 'teapot'), /오류 418/);
  assert.equal(messageForStatus(undefined, 'x'), MESSAGES.unknown);
  for (const text of Object.values(MESSAGES)) assert.match(text, /[가-힣]/);
});

test('browser network wordings and unknown things become Korean, with the caller\'s Korean fallback when it is sensible', () => {
  for (const text of ['Failed to fetch', 'NetworkError when attempting to fetch resource.', 'Load failed', 'network request failed']) {
    assert.equal(errorText(new Error(text), '실패'), MESSAGES.network, text);
    assert.equal(isNetworkError(new Error(text)), true);
  }
  assert.equal(errorText(new TypeError('whatever'), '실패'), MESSAGES.network);
  assert.equal(errorText('boom', '목록을 불러오지 못했습니다.'), '목록을 불러오지 못했습니다.');
  assert.equal(errorText(new Error('Unexpected token < in JSON'), 'fallback in English'), MESSAGES.unknown);
  assert.equal(errorText(undefined), MESSAGES.unknown);
});

test('a failed fetch response is read for Korean text only; English detail or an empty body falls back to the status text', async () => {
  const res = (status, body) => new Response(typeof body === 'string' ? body : JSON.stringify(body), { status });
  assert.equal(await responseErrorText(res(503, { detail: 'Service Unavailable' })), MESSAGES.server);
  assert.equal(await responseErrorText(res(409, { detail: { code: 'X', message: 'Draft must be approved' } })), MESSAGES.conflict);
  assert.equal(await responseErrorText(res(422, { detail: '입력을 확인해 주세요: 이름' })), '입력을 확인해 주세요: 이름');
  assert.equal(await responseErrorText(res(500, 'not json at all')), MESSAGES.server);
  assert.equal(await responseErrorText(res(401, {})), MESSAGES.unauthorized);
});

test('sign-in failures: known provider texts get an exact Korean sentence, the rest a safe Korean fallback, never English', () => {
  assert.equal(authErrorText(new Error('Invalid login credentials')), '이메일 또는 비밀번호가 올바르지 않습니다.');
  assert.equal(authErrorText(new Error('Email not confirmed')), '이메일 인증을 완료한 뒤 로그인해 주세요.');
  assert.equal(authErrorText(new Error('User already registered')), '이미 가입된 이메일입니다. 로그인해 주세요.');
  assert.equal(authErrorText(new Error('Password should be at least 8 characters')), '비밀번호는 8자 이상이어야 합니다.');
  assert.equal(authErrorText(new TypeError('Failed to fetch')), MESSAGES.network);
  assert.equal(authErrorText(new Error('이메일 인증 여부를 확인해 주세요.')), '이메일 인증 여부를 확인해 주세요.');
  assert.equal(authErrorText(new Error('Something unexpected happened')), AUTH_FALLBACK);
  assert.equal(authErrorText(undefined), AUTH_FALLBACK);
  assert.ok(!ENGLISH.test(AUTH_FALLBACK));
});
