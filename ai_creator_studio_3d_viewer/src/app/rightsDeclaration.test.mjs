import test from 'node:test';
import assert from 'node:assert/strict';
import { appendRightsDeclaration, rightsErrorCode } from './rightsDeclaration.mjs';

const fields = form => Object.fromEntries(form.entries());

test('the declaration is sent as explicit booleans', () => {
  assert.deepEqual(fields(appendRightsDeclaration(new FormData(), { rightsConfirmed: true, depictsPerson: false, likenessConsent: false })),
    { rights_confirmed: 'true', depicts_person: 'false', likeness_consent: 'false' });
  assert.deepEqual(fields(appendRightsDeclaration(new FormData(), { rightsConfirmed: false, depictsPerson: false, likenessConsent: false })),
    { rights_confirmed: 'false', depicts_person: 'false', likeness_consent: 'false' });
});

test('likeness consent is only sent as true when a person is shown', () => {
  assert.equal(fields(appendRightsDeclaration(new FormData(), { rightsConfirmed: true, depictsPerson: true, likenessConsent: true })).likeness_consent, 'true');
  assert.equal(fields(appendRightsDeclaration(new FormData(), { rightsConfirmed: true, depictsPerson: false, likenessConsent: true })).likeness_consent, 'false');
  assert.equal(fields(appendRightsDeclaration(new FormData(), { rightsConfirmed: true, depictsPerson: true, likenessConsent: false })).likeness_consent, 'false');
});

test('only the two rights error codes are recognised', async () => {
  const res = (detail, status = 422) => new Response(JSON.stringify({ detail }), { status });
  assert.equal(await rightsErrorCode(res({ code: 'RIGHTS_CONFIRMATION_REQUIRED', message: 'x' })), 'RIGHTS_CONFIRMATION_REQUIRED');
  assert.equal(await rightsErrorCode(res({ code: 'LIKENESS_CONSENT_REQUIRED', message: 'x' })), 'LIKENESS_CONSENT_REQUIRED');
  assert.equal(await rightsErrorCode(res({ code: 'ASSET_FORMAT_UNSUPPORTED', message: 'x' })), null);
  assert.equal(await rightsErrorCode(res('plain string detail')), null);
  assert.equal(await rightsErrorCode(new Response('not json', { status: 500 })), null);
});

test('reading the error does not consume the response body for later readers', async () => {
  const response = new Response(JSON.stringify({ detail: { code: 'RIGHTS_CONFIRMATION_REQUIRED', message: 'm' } }), { status: 422 });
  await rightsErrorCode(response);
  assert.equal((await response.json()).detail.message, 'm');
});
