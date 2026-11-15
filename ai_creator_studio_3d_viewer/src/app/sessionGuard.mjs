// R-030 A: any 401 from OUR API means the login is no longer accepted. This watches API responses in one place (every screen, whether it
// uses apiRequest or its own fetch) and reports it; the app then asks for the password again WITHOUT leaving the screen, so what the
// person was typing is not lost. Other addresses (Supabase, images from elsewhere) are never inspected.
export const normalizeApiBase = (value) => String(value || '').trim().replace(/\/+$/, '');

export function isApiUrl(url, apiBase) {
  const base = normalizeApiBase(apiBase);
  return !!base && typeof url === 'string' && (url === base || url.startsWith(`${base}/`));
}

const urlOf = (input) => (typeof input === 'string' ? input : input?.url ?? (input instanceof URL ? input.href : ''));

// Returns a fetch that behaves exactly like `original` and additionally calls onUnauthorized() once per 401 from the API.
// /health is exempt (an unauthenticated probe); a failure inside the callback never changes the response.
export function wrapFetch(original, { getApiBase, onUnauthorized }) {
  return async function guardedFetch(input, init) {
    const response = await original(input, init);
    try {
      const url = urlOf(input);
      if (response.status === 401 && isApiUrl(url, getApiBase()) && !/\/health(\?|$)/.test(url)) onUnauthorized();
    } catch { /* never let the watcher break a request */ }
    return response;
  };
}

export function installUnauthorizedWatcher({ getApiBase, onUnauthorized, target = globalThis }) {
  const original = target.fetch;
  if (typeof original !== 'function') return () => undefined;
  const wrapped = wrapFetch(original.bind(target), { getApiBase, onUnauthorized });
  target.fetch = wrapped;
  return () => { if (target.fetch === wrapped) target.fetch = original; };
}
