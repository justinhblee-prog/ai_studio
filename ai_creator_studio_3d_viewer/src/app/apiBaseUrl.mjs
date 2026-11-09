// L-13: where the Backend API address comes from.
// Release (production) builds use ONLY the build-time VITE_API_BASE_URL. There is no user-editable
// address, no localStorage override and no localhost fallback, so a release bundle cannot be pointed
// at another server from the browser. Development builds keep the editable, remembered address.
export const API_BASE_STORAGE_KEY = 'acs.backend.baseUrl';

function clean(value) {
  return String(value ?? '').trim().replace(/\/+$/, '');
}

export function isApiBaseEditable({ production }) {
  return !production;
}

// `readSaved` is injected so callers can wrap storage access in try/catch.
export function resolveApiBase({ production, configured, readSaved = () => '', hostname = '' }) {
  const fixed = clean(configured);
  if (production) return fixed; // empty means the release build is misconfigured; never guess.
  if (fixed) return fixed;
  const saved = clean(readSaved());
  if (saved) return saved;
  return ['localhost', '127.0.0.1'].includes(hostname) ? 'http://localhost:8000' : '';
}

export function apiBaseConfigError({ production, base }) {
  if (!production || clean(base)) return '';
  return '이 빌드에는 Backend API 주소(VITE_API_BASE_URL)가 설정되어 있지 않습니다. 운영자에게 문의해 주세요.';
}
