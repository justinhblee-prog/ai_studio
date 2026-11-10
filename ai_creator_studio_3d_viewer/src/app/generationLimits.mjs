// Korean user-facing messages for the backend's 429 cost-cap codes (app/cost_cap.py, app/main.py).
// Internal limit values (limit/used) and the server's English message are never shown.
export const GENERATION_LIMIT_MESSAGES = Object.freeze({
  AI_JOBS_DISABLED: 'AI 생성이 잠시 중단되었습니다. 잠시 후 다시 시도해 주세요.',
  DAILY_JOB_LIMIT_EXCEEDED: '오늘 생성 한도에 도달했습니다. 내일 다시 시도해 주세요.',
  WORKSPACE_MONTHLY_LIMIT: '이번 달 생성 한도에 도달했습니다. 다음 달에 다시 시도해 주세요.',
  GLOBAL_MONTHLY_LIMIT: '현재 서비스 전체 생성 한도에 도달해 새 생성을 받을 수 없습니다. 잠시 후 다시 시도해 주세요.',
});

// Returns the Korean message for a known cap code, or null for anything else.
export function generationLimitMessage(code) {
  return Object.prototype.hasOwnProperty.call(GENERATION_LIMIT_MESSAGES, code) ? GENERATION_LIMIT_MESSAGES[code] : null;
}
