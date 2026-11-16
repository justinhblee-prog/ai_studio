// R-037: the "your photos are sent to an external AI service" notice. The server refuses a real-provider job with 409 EXTERNAL_NOTICE_REQUIRED
// (carrying the provider and its data-handling facts) until the member has acknowledged it once; this module turns that answer into text.
import { apiRequest } from './apiClient.mjs';

export const NOTICE_CODE = 'EXTERNAL_NOTICE_REQUIRED';

// Returns {provider, lines[]} when `error` is that refusal, else null. Unknown facts are said to be unknown, never glossed over.
export function noticeFromError(error) {
  if (error?.code !== NOTICE_CODE) return null;
  const provider = String(error.detail?.provider || '외부 AI 서비스');
  const policy = error.detail?.data_policy || {};
  const lines = [`이 작업은 외부 AI 서비스(${provider})로 사진이 전송됩니다.`];
  if (policy.trains_on_customer_content === false) lines.push('공급자 문서상 전송한 사진을 AI 학습에 사용하지 않는다고 되어 있습니다.');
  else if (policy.trains_on_customer_content === true) lines.push('공급자가 전송한 사진을 AI 학습에 사용할 수 있습니다.');
  else lines.push('공급자가 사진을 AI 학습에 사용하는지 확인되지 않았습니다.');
  if (policy.input_retention) lines.push(`보관: ${policy.input_retention}`);
  if (policy.output_retention) lines.push(`결과물: ${policy.output_retention}`);
  if (policy.request_log_deletion) lines.push(`삭제 요청: ${policy.request_log_deletion}`);
  if (policy.terms_check_required !== false) lines.push('위 내용은 공급자 문서를 읽은 것이며 공급자 약관 확인이 필요합니다.');
  return { provider, lines };
}

export const acknowledgeNotice = (api, token, workspaceId, provider) =>
  apiRequest(api, '/v1/external-provider-notices', { token, method: 'POST', body: { workspace_id: workspaceId, provider } });
