const SESSION_KEY = 'acs.auth.session.v1';

export function normalizeSupabaseConfig(config = {}) {
  const url = String(config.url || '').trim().replace(/\/+$/, '');
  const anonKey = String(config.anonKey || '').trim();
  return { url, anonKey, configured: Boolean(url && anonKey) };
}

async function authRequest(config, path, { method = 'GET', body, accessToken, fetchImpl = fetch } = {}) {
  const normalized = normalizeSupabaseConfig(config);
  if (!normalized.configured) throw new Error('Supabase URL과 Publishable/anon Key 설정이 필요합니다.');
  const headers = { apikey: normalized.anonKey, Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  const response = await fetchImpl(`${normalized.url}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = typeof payload?.msg === 'string' ? payload.msg
      : typeof payload?.message === 'string' ? payload.message
      : typeof payload?.error_description === 'string' ? payload.error_description
      : typeof payload?.error === 'string' ? payload.error
      : `인증 요청 실패 (${response.status})`;
    throw new Error(message);
  }
  return payload;
}

function normalizeSession(payload) {
  if (!payload?.access_token || !payload?.refresh_token) return null;
  const expiresIn = Number(payload.expires_in || 3600);
  return {
    access_token: payload.access_token,
    refresh_token: payload.refresh_token,
    token_type: payload.token_type || 'bearer',
    expires_at: Number(payload.expires_at || (Math.floor(Date.now() / 1000) + expiresIn)),
    user: payload.user || null,
  };
}

export async function signInWithPassword(config, email, password, fetchImpl) {
  const payload = await authRequest(config, '/auth/v1/token?grant_type=password', {
    method: 'POST', body: { email: email.trim(), password }, fetchImpl,
  });
  const session = normalizeSession(payload);
  if (!session) throw new Error('로그인 응답에 유효한 세션이 없습니다. 이메일 인증 여부를 확인해 주세요.');
  return session;
}

export async function signUpWithPassword(config, email, password, fetchImpl) {
  const payload = await authRequest(config, '/auth/v1/signup', {
    method: 'POST', body: { email: email.trim(), password }, fetchImpl,
  });
  return { user: payload.user || payload, session: normalizeSession(payload) };
}

export async function getAuthenticatedUser(config, accessToken, fetchImpl) {
  return authRequest(config, '/auth/v1/user', { accessToken, fetchImpl });
}

export async function refreshSession(config, session, fetchImpl) {
  if (!session?.refresh_token) throw new Error('세션 갱신 토큰이 없습니다. 다시 로그인해 주세요.');
  const payload = await authRequest(config, '/auth/v1/token?grant_type=refresh_token', {
    method: 'POST', body: { refresh_token: session.refresh_token }, fetchImpl,
  });
  const next = normalizeSession(payload);
  if (!next) throw new Error('세션 갱신 응답이 올바르지 않습니다.');
  return next;
}

export async function signOut(config, session, fetchImpl) {
  if (!session?.access_token) return;
  await authRequest(config, '/auth/v1/logout', { method: 'POST', accessToken: session.access_token, fetchImpl });
}

export function saveSession(session, storage = globalThis.sessionStorage) {
  if (!storage) return;
  storage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function loadSession(storage = globalThis.sessionStorage) {
  if (!storage) return null;
  try {
    const session = normalizeSession(JSON.parse(storage.getItem(SESSION_KEY) || 'null'));
    if (!session || session.expires_at <= Math.floor(Date.now() / 1000)) return null;
    return session;
  } catch {
    return null;
  }
}

export function clearSession(storage = globalThis.sessionStorage) {
  storage?.removeItem(SESSION_KEY);
}

export function sessionFromLocationHash(hash = globalThis.location?.hash || '') {
  const values = new URLSearchParams(hash.startsWith('#') ? hash.slice(1) : hash);
  const accessToken = values.get('access_token');
  const refreshToken = values.get('refresh_token');
  if (!accessToken || !refreshToken) return null;
  return normalizeSession({
    access_token: accessToken,
    refresh_token: refreshToken,
    token_type: values.get('token_type') || 'bearer',
    expires_in: values.get('expires_in') || 3600,
  });
}
