/** Resolve the base path passed to GLTFLoader.parse for an HTTP(S) model URL. */
export function resolveModelBasePath(modelUrl, pageUrl) {
  let resolved;
  try {
    resolved = new URL(modelUrl, pageUrl);
  } catch {
    throw new TypeError('Model URL must be a valid absolute or page-relative URL.');
  }
  if (resolved.protocol !== 'http:' && resolved.protocol !== 'https:') {
    throw new TypeError('Model URL must use HTTP or HTTPS.');
  }
  return new URL('.', resolved).toString();
}
