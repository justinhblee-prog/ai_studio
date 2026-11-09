import test from 'node:test';
import assert from 'node:assert/strict';
import {
  normalizeSupabaseConfig, signInWithPassword, signUpWithPassword,
  getAuthenticatedUser, refreshSession, saveSession, loadSession, clearSession,
  sessionFromLocationHash,
} from './supabaseAuth.mjs';
import { apiRequest, createWorkspaceId, loadOrCreateWorkspace } from './apiClient.mjs';

const config = { url: 'https://example.supabase.co/', anonKey: 'public-key' };
const session = { access_token: 'access', refresh_token: 'refresh', expires_in: 3600, user: { id: 'u1' } };

function response(payload, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => payload };
}

test('Supabase config normalization trims URL and requires both public settings', () => {
  assert.deepEqual(normalizeSupabaseConfig(config), { url: 'https://example.supabase.co', anonKey: 'public-key', configured: true });
  assert.equal(normalizeSupabaseConfig({ url: config.url }).configured, false);
});

test('password login calls Supabase Auth and normalizes the session', async () => {
  let call;
  const result = await signInWithPassword(config, ' user@example.com ', 'password', async (url, options) => {
    call = { url, options }; return response(session);
  });
  assert.equal(call.url, 'https://example.supabase.co/auth/v1/token?grant_type=password');
  assert.equal(JSON.parse(call.options.body).email, 'user@example.com');
  assert.equal(result.access_token, 'access');
  assert.ok(result.expires_at > 0);
});

test('signup returns a confirmation-required result when Supabase has no session', async () => {
  const result = await signUpWithPassword(config, 'new@example.com', 'password', async () => response({ user: { id: 'u2' } }));
  assert.equal(result.user.id, 'u2');
  assert.equal(result.session, null);
});

test('authenticated user and refresh requests carry bearer token', async () => {
  const seen = [];
  const fetchImpl = async (url, options) => { seen.push({ url, options }); return response(url.endsWith('/user') ? { id: 'u1' } : { ...session, expires_in: 3600 }); };
  assert.equal((await getAuthenticatedUser(config, 'access', fetchImpl)).id, 'u1');
  assert.equal((await refreshSession(config, session, fetchImpl)).access_token, 'access');
  assert.equal(seen[0].options.headers.Authorization, 'Bearer access');
  assert.equal(JSON.parse(seen[1].options.body).refresh_token, 'refresh');
});

test('session storage and email-link hash parsing are bounded and defensive', () => {
  const data = new Map();
  const storage = { setItem: (k, v) => data.set(k, v), getItem: (k) => data.get(k) || null, removeItem: (k) => data.delete(k) };
  saveSession({ ...session, expires_at: Math.floor(Date.now() / 1000) + 600 }, storage);
  assert.equal(loadSession(storage).access_token, 'access');
  clearSession(storage);
  assert.equal(loadSession(storage), null);
  assert.equal(sessionFromLocationHash('#access_token=a&refresh_token=r&expires_in=600').access_token, 'a');
  assert.equal(sessionFromLocationHash('#error=access_denied'), null);
});

test('workspace id is URL-safe and workspace bootstrap creates only when empty', async () => {
  assert.match(createWorkspaceId(() => '12345678-1234-1234-1234-123456789012'), /^ws_[a-f0-9]{24}$/);
  const calls = [];
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    if (options.method === 'POST') return response({ workspace_id: JSON.parse(options.body).workspace_id, role: 'owner' }, 201);
    return response({ items: [] });
  };
  try {
    const result = await loadOrCreateWorkspace('https://api.example.com', 'token');
    assert.equal(result.workspaces.length, 1);
    assert.equal(calls.length, 2);
    assert.equal(calls[1].options.headers.Authorization, 'Bearer token');
  } finally { globalThis.fetch = originalFetch; }
});

test('API client rejects insecure non-local HTTP endpoints', async () => {
  await assert.rejects(() => apiRequest('http://api.example.com', '/health'), /HTTPS/);
  await assert.doesNotReject(() => apiRequest('http://localhost:8000', '/health', { token: 't' }).catch((error) => {
    if (!String(error.message).includes('fetch')) throw error;
  }));
});

test('API client sends JSON and maps backend errors', async () => {
  const originalFetch = globalThis.fetch;
  let seen;
  globalThis.fetch = async (url, options) => { seen = { url, options }; return response({ ok: true }); };
  try {
    await apiRequest('https://api.example.com/', '/v1/test', { token: 't', method: 'POST', body: { value: 1 } });
    assert.equal(seen.url, 'https://api.example.com/v1/test');
    assert.equal(seen.options.headers.Authorization, 'Bearer t');
    assert.equal(JSON.parse(seen.options.body).value, 1);
  } finally { globalThis.fetch = originalFetch; }
});
