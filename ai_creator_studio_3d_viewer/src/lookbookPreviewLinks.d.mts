export function getSignedDownloadExpiry(value: string, baseUrl?: string): number | null;
export function isSignedLinkUsable(expiry: number | null, nowSeconds?: number): boolean;
export function isCurrentPreviewUrl(currentUrl: string | undefined, failedUrl: string | undefined): boolean;
