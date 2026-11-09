export const MAX_MODEL_DOWNLOAD_BYTES: number;
export type ModelDownloadErrorCode = 'unauthorized' | 'forbidden' | 'not_found' | 'conflict' | 'too_large' | 'memory' | 'http' | 'network' | 'invalid_body';
export class ModelDownloadError extends Error { readonly status?: number; readonly code: ModelDownloadErrorCode; constructor(code: ModelDownloadErrorCode, message: string, status?: number); }
export function readModelResponse(response: Response, signal: AbortSignal, onProgress?: (value: number) => void): Promise<ArrayBuffer>;
export function getHttpDownloadError(status: number): ModelDownloadError;
