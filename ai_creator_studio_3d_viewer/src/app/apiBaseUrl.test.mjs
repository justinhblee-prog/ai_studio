import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveApiBase, isApiBaseEditable, apiBaseConfigError } from './apiBaseUrl.mjs';

test('release build uses only the build-time address and ignores saved or localhost values', () => {
  const saved = () => 'https://attacker.example';
  assert.equal(resolveApiBase({ production: true, configured: 'https://api.example.com/', readSaved: saved, hostname: 'localhost' }), 'https://api.example.com');
  assert.equal(resolveApiBase({ production: true, configured: '', readSaved: saved, hostname: 'localhost' }), '');
  assert.equal(resolveApiBase({ production: true, configured: '   ', readSaved: saved, hostname: '127.0.0.1' }), '');
});

test('release build is never editable; development build is', () => {
  assert.equal(isApiBaseEditable({ production: true }), false);
  assert.equal(isApiBaseEditable({ production: false }), true);
});

test('release build without an address reports a configuration error instead of guessing', () => {
  assert.match(apiBaseConfigError({ production: true, base: '' }), /VITE_API_BASE_URL/);
  assert.equal(apiBaseConfigError({ production: true, base: 'https://api.example.com' }), '');
  assert.equal(apiBaseConfigError({ production: false, base: '' }), '');
});

test('development build keeps the previous order: env, remembered value, localhost, empty', () => {
  assert.equal(resolveApiBase({ production: false, configured: 'https://env.example', readSaved: () => 'https://saved.example' }), 'https://env.example');
  assert.equal(resolveApiBase({ production: false, configured: '', readSaved: () => 'https://saved.example/' }), 'https://saved.example');
  assert.equal(resolveApiBase({ production: false, configured: '', hostname: 'localhost' }), 'http://localhost:8000');
  assert.equal(resolveApiBase({ production: false, configured: '', hostname: 'studio.example.com' }), '');
});
