export function normalizeApiBase(value: unknown): string;
export function isApiUrl(url: unknown, apiBase: unknown): boolean;
export function wrapFetch(original: typeof fetch, options: { getApiBase: () => string; onUnauthorized: () => void }): typeof fetch;
export function installUnauthorizedWatcher(options: { getApiBase: () => string; onUnauthorized: () => void; target?: { fetch: typeof fetch } }): () => void;
