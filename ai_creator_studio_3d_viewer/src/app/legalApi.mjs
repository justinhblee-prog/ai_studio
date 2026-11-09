// L-02 / L-01 client helpers: legal acceptance, the separate AI-training consent, and deletion requests.
// Pure functions over apiRequest so they can be tested with a fake fetch. No legal text lives here.
import { apiRequest } from './apiClient.mjs';

export const DOCUMENT_LABELS = { terms: '이용약관', privacy: '개인정보 처리방침', content_policy: '콘텐츠 정책' };

export const loadLegalStatus = (api, token) => apiRequest(api, '/v1/me/legal-status', { token });

// Accepts exactly the versions the server reports as required; the caller cannot pick another version.
export function acceptRequired(api, token, status) {
  const documents = (status?.missing?.length ? status.missing : status?.required || []).map(d => ({ document: d.document, version: d.version }));
  if (!documents.length) return Promise.resolve(status);
  return apiRequest(api, '/v1/me/legal-acceptances', { token, method: 'POST', body: { documents } });
}

export const loadConsents = async (api, token) => (await apiRequest(api, '/v1/me/consents', { token }))?.items || [];
export const setConsent = async (api, token, purpose, granted) =>
  (await apiRequest(api, `/v1/me/consents/${encodeURIComponent(purpose)}`, { token, method: 'PUT', body: { granted: Boolean(granted) } }))?.items || [];

export const loadDeletionRequests = async (api, token) => (await apiRequest(api, '/v1/me/deletion-requests', { token }))?.items || [];
export const requestAccountDeletion = (api, token, reason) =>
  apiRequest(api, '/v1/me/deletion-requests', { token, method: 'POST', body: reason?.trim() ? { scope: 'account', reason: reason.trim() } : { scope: 'account' } });
export const cancelDeletionRequest = (api, token, requestId) =>
  apiRequest(api, `/v1/me/deletion-requests/${encodeURIComponent(requestId)}`, { token, method: 'DELETE' });

// The gate is shown only when the server says something is missing. A failed status check is NOT treated as accepted.
export function gateState(status, error) {
  if (error) return 'error';
  if (!status) return 'loading';
  return status.accepted ? 'open' : 'needs-acceptance';
}
