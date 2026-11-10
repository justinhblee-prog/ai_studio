// Korean user-facing messages for the backend's 429 cost-cap codes (app/cost_cap.py, app/main.py).
// Service-wide stops (kill switch, global limit) are worded so the user is not blamed. The server's English message is never shown;
// the per-workspace daily limit shows its own numbers when the server sends them (the monthly responses carry none).
export const GENERATION_LIMIT_MESSAGES = Object.freeze({
  AI_JOBS_DISABLED: '서비스 사정으로 AI 생성이 잠시 중단되었습니다. 잠시 후 다시 시도하거나 운영자에게 문의해 주세요.',
  DAILY_JOB_LIMIT_EXCEEDED: '오늘 생성 한도에 도달했습니다. 내일 다시 시도해 주세요.',
  WORKSPACE_MONTHLY_LIMIT: '이번 달 생성 한도에 도달했습니다. 다음 달에 다시 시도해 주세요.',
  GLOBAL_MONTHLY_LIMIT: '서비스 사정으로 지금은 새 AI 생성을 받을 수 없습니다. 잠시 후 다시 시도하거나 운영자에게 문의해 주세요.',
});

// Returns the Korean message for a known cap code, or null for anything else.
export function generationLimitMessage(code, detail) {
  if (!Object.prototype.hasOwnProperty.call(GENERATION_LIMIT_MESSAGES, code)) return null;
  const base = GENERATION_LIMIT_MESSAGES[code];
  const { limit, used } = detail || {};
  if (code === 'DAILY_JOB_LIMIT_EXCEEDED' && Number.isInteger(limit) && Number.isInteger(used)) return `${base} (오늘 ${used}/${limit}건)`;
  return base;
}
