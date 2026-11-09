/** Read the short-lived signature expiry from a Lookbook package download URL. */
export function getSignedDownloadExpiry(value, baseUrl = 'http://localhost') {
  try {
    const parsed = new URL(value, baseUrl);
    const raw = parsed.searchParams.get('expires');
    if (!raw || !/^\d+$/.test(raw)) return null;
    const expiry = Number(raw);
    return Number.isSafeInteger(expiry) && expiry > 0 ? expiry : null;
  } catch {
    return null;
  }
}

/** A signed URL is usable only while its server-issued expiry is in the future. */
export function isSignedLinkUsable(expiry, nowSeconds = Math.floor(Date.now() / 1000)) {
  return Number.isSafeInteger(expiry) && expiry > nowSeconds;
}

/** Ignore delayed image errors unless they refer to the URL currently displayed. */
export function isCurrentPreviewUrl(currentUrl, failedUrl) {
  return typeof failedUrl === 'string' && failedUrl.length > 0 && currentUrl === failedUrl;
}
