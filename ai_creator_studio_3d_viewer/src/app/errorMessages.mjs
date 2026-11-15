// R-030 B: one place that turns any failure into Korean text for the screens. The server's English wording (and the browser's
// "Failed to fetch") is never shown; a message that is already Korean (the app's own, or a Korean server text) passes through.
const HANGUL = /[가-힣]/;
const GENERIC_STATUS_TEXT = /^(API )?요청 실패 \(\d+\)$/;

export const MESSAGES = Object.freeze({
  network: '네트워크에 연결할 수 없습니다. 인터넷 연결을 확인한 뒤 다시 시도해 주세요.',
  unauthorized: '로그인이 만료되었습니다. 다시 로그인해 주세요.',
  forbidden: '이 작업을 할 권한이 없습니다. 작업공간 관리자에게 문의해 주세요.',
  notFound: '요청한 항목을 찾을 수 없습니다. 이미 삭제되었거나 권한이 없을 수 있습니다.',
  conflict: '현재 상태에서는 처리할 수 없습니다. 화면을 새로고침한 뒤 다시 시도해 주세요.',
  tooLarge: '파일이 너무 큽니다. 더 작은 파일로 다시 시도해 주세요.',
  invalid: '입력한 내용을 확인해 주세요.',
  tooMany: '요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.',
  server: '서버에 문제가 생겨 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.',
  unknown: '알 수 없는 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.',
});

const isKorean = (text) => typeof text === 'string' && HANGUL.test(text) && !GENERIC_STATUS_TEXT.test(text.trim());

export function messageForStatus(status, serverText) {
  if (isKorean(serverText)) return serverText.trim();
  switch (status) {
    case 401: return MESSAGES.unauthorized;
    case 403: return MESSAGES.forbidden;
    case 404: return MESSAGES.notFound;
    case 409: return MESSAGES.conflict;
    case 413: return MESSAGES.tooLarge;
    case 400: case 422: return MESSAGES.invalid;
    case 429: return MESSAGES.tooMany;
    default:
      if (Number.isInteger(status) && status >= 500) return MESSAGES.server;
      if (Number.isInteger(status) && status >= 400) return `요청을 처리하지 못했습니다 (오류 ${status}).`;
      return MESSAGES.unknown;
  }
}

const NETWORK_TEXT = /failed to fetch|networkerror|network request failed|load failed|fetch failed|network error|err_connection|aborted/i;
export const isNetworkError = (reason) => reason instanceof TypeError || (reason instanceof Error && !reason.status && NETWORK_TEXT.test(reason.message));

// For catch blocks: errorText(reason, 'what we were doing failed'). `reason` may be an Error from apiRequest (has .status), a TypeError from
// fetch, an Error with our own Korean text, or anything else.
export function errorText(reason, fallback) {
  if (isNetworkError(reason)) return MESSAGES.network;
  if (reason instanceof Error) {
    if (Number.isInteger(reason.status)) return messageForStatus(reason.status, reason.message);
    if (isKorean(reason.message)) return reason.message;
  }
  return fallback && isKorean(fallback) ? fallback : MESSAGES.unknown;
}

// For fetch responses that are not ok: the text of the server's `detail` (string or {message}) decides only if it is already Korean.
export async function responseErrorText(response) {
  let serverText = '';
  try {
    const detail = (await response.json())?.detail;
    serverText = typeof detail === 'string' ? detail : detail?.message || '';
  } catch { /* no JSON body */ }
  return messageForStatus(response.status, serverText);
}

// Sign-in / sign-up failures come from the identity provider (English text). Known cases get a precise Korean sentence.
const AUTH_CASES = [
  [/invalid login credentials|invalid credentials|invalid_grant/i, '이메일 또는 비밀번호가 올바르지 않습니다.'],
  [/email not confirmed/i, '이메일 인증을 완료한 뒤 로그인해 주세요.'],
  [/already registered|already been registered|user already exists/i, '이미 가입된 이메일입니다. 로그인해 주세요.'],
  [/password should be at least|weak password|password is too short/i, '비밀번호는 8자 이상이어야 합니다.'],
  [/rate limit|too many requests|over_.*_rate_limit/i, '시도가 너무 많습니다. 잠시 후 다시 시도해 주세요.'],
  [/unable to validate email|invalid email|email address .* is invalid/i, '이메일 주소 형식이 올바르지 않습니다.'],
];
export const AUTH_FALLBACK = '로그인하지 못했습니다. 이메일과 비밀번호를 확인한 뒤 다시 시도해 주세요.';
export function authErrorText(reason) {
  if (isNetworkError(reason)) return MESSAGES.network;
  const message = reason instanceof Error ? reason.message : '';
  if (isKorean(message)) return message;
  const known = AUTH_CASES.find(([pattern]) => pattern.test(message));
  return known ? known[1] : AUTH_FALLBACK;
}
