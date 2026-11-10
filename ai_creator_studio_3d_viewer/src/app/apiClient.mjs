import { generationLimitMessage } from './generationLimits.mjs';

export async function apiRequest(baseUrl, path, { token, method = 'GET', body, signal } = {}) {
  const base = String(baseUrl || '').trim().replace(/\/+$/, '');
  if (!base) throw new Error('Backend API 주소가 설정되지 않았습니다.');
  let parsed;
  try { parsed = new URL(base); } catch { throw new Error('Backend API 주소 형식이 올바르지 않습니다.'); }
  const localHost = ['localhost', '127.0.0.1', '[::1]'].includes(parsed.hostname);
  if (parsed.protocol !== 'https:' && !(parsed.protocol === 'http:' && localHost)) {
    throw new Error('실서비스 Backend API는 HTTPS 주소를 사용해야 합니다.');
  }
  const headers = { Accept: 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const response = await fetch(`${base}${path}`, {
    method, headers, signal,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (response.status === 204) return null;
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload?.detail;
    const limitText = response.status === 429 ? generationLimitMessage(detail?.code) : null;
    if (limitText) throw Object.assign(new Error(limitText), { code: detail.code });
    throw new Error(typeof detail === 'string' ? detail : detail?.message || `API 요청 실패 (${response.status})`);
  }
  return payload;
}

export function createWorkspaceId(randomUUID = () => globalThis.crypto.randomUUID()) {
  return `ws_${randomUUID().replace(/-/g, '').slice(0, 24)}`;
}

export async function loadOrCreateWorkspace(baseUrl, token) {
  const result = await apiRequest(baseUrl, '/v1/workspaces', { token });
  const existing = Array.isArray(result?.items) ? result.items : [];
  if (existing.length) return { workspace: existing[0], workspaces: existing };
  const created = await apiRequest(baseUrl, '/v1/workspaces', {
    token, method: 'POST', body: { workspace_id: createWorkspaceId() },
  });
  return { workspace: created, workspaces: [created] };
}
