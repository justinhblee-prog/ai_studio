// R-027: job list / status / result viewing for the try-on test generation (mock provider only, existing read APIs only).
import { apiRequest } from './apiClient.mjs';

// Backend JobStatus -> the 4 states shown to people (queued=대기, running+post_processing=진행, succeeded=완료, failed=실패).
const GROUPS = { queued: 'waiting', running: 'running', post_processing: 'running', succeeded: 'done', failed: 'failed' };
export const STATUS_LABELS = { waiting: '대기', running: '진행', done: '완료', failed: '실패', unknown: '알 수 없음' };
export const statusGroup = (status) => GROUPS[status] ?? 'unknown';
export const statusLabel = (status) => STATUS_LABELS[statusGroup(status)];
export const isActive = (status) => ['waiting', 'running'].includes(statusGroup(status));

export const EMPTY_LIST_MESSAGE = '아직 생성 작업이 없습니다. "가상 착장 시험 생성"에서 작업을 시작해 보세요.';
export const NO_RESULT_MESSAGE = '표시할 결과 이미지가 없습니다. 시험(mock) 엔진은 실제 이미지를 만들지 않습니다.';
export const TEST_MARK = '시험 생성';

const FAILURE_MESSAGES = {
  PROVIDER_GENERATION_FAILED: '생성 엔진이 작업을 완료하지 못했습니다. 잠시 후 다시 시도해 주세요.',
  PROVIDER_OUTPUT_MISSING: '생성은 끝났지만 결과 이미지를 받지 못했습니다. 다시 시도해 주세요.',
  PROVIDER_START_UNKNOWN: '작업이 엔진에 접수되었는지 확인되지 않았습니다. 운영자 확인이 필요합니다.',
  OUTPUT_SAVE_PENDING: '결과 이미지를 저장하는 중입니다. 잠시 후 새로고침해 주세요.',
  JOB_CANCELLED: '작업이 취소되었습니다.',
};
// Korean text for a failed job; never shows the server's English message or raw code as the main text.
export const failureMessage = (errorCode) => FAILURE_MESSAGES[errorCode] ?? '생성에 실패했습니다. 다시 시도해 주세요. 계속되면 운영자에게 알려 주세요.';

export const listGenerationJobs = (api, token, workspaceId, { limit = 50, offset = 0 } = {}) =>
  apiRequest(api, `/v1/generation-jobs?workspace_id=${encodeURIComponent(workspaceId)}&limit=${limit}&offset=${offset}`, { token });

export async function listJobOutputs(api, token, jobId) {
  const result = await apiRequest(api, `/v1/generation-jobs/${encodeURIComponent(jobId)}/outputs`, { token });
  return Array.isArray(result?.data) ? result.data : [];
}

// Only a succeeded job can show a result, and only when the server really has an image for it.
export async function loadJobResultBlob(api, token, job) {
  if (statusGroup(job?.status) !== 'done' || !job.output_url) return null;
  const base = String(api || '').trim().replace(/\/+$/, '');
  const response = await fetch(`${base}/v1/generation-jobs/${encodeURIComponent(job.job_id)}/output`, { headers: { Authorization: `Bearer ${token}` } });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`결과 이미지를 불러오지 못했습니다 (${response.status})`);
  return response.blob();
}
