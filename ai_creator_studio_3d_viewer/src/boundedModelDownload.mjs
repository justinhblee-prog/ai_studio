export const MAX_MODEL_DOWNLOAD_BYTES = 256 * 1024 * 1024;

export class ModelDownloadError extends Error {
  constructor(code, message, status) {
    super(message);
    this.name = 'ModelDownloadError';
    this.code = code;
    this.status = status;
  }
}

async function cancelResponseBody(response, reason) {
  try {
    if (response.body && !response.body.locked) await response.body.cancel(reason);
  } catch { /* cancellation is best-effort; the typed download error remains authoritative */ }
}

/**
 * Read a Fetch response with a hard byte ceiling and abort-aware stream cleanup.
 * When Content-Length is valid, allocate the final buffer once to avoid retaining
 * every chunk and then allocating a second full-size copy at completion.
 */
export async function readModelResponse(response, signal, onProgress = () => {}) {
  const rawLength = response.headers.get('content-length');
  let declaredLength = null;
  if (rawLength !== null) {
    if (!/^(0|[1-9][0-9]*)$/.test(rawLength)) {
      await cancelResponseBody(response, 'Invalid Content-Length.');
      throw new ModelDownloadError('network', 'Model response length header is invalid.');
    }
    const parsedLength = BigInt(rawLength);
    if (parsedLength > BigInt(MAX_MODEL_DOWNLOAD_BYTES)) {
      await cancelResponseBody(response, 'Model exceeds the client download limit.');
      throw new ModelDownloadError('too_large', 'Model exceeds the client download limit.');
    }
    declaredLength = Number(parsedLength);
  }
  if (!response.body || typeof response.body.getReader !== 'function') {
    throw new ModelDownloadError('invalid_body', 'Streaming response body is unavailable.');
  }
  if (signal?.aborted) {
    await cancelResponseBody(response, 'Model download aborted.');
    throw new DOMException('Aborted', 'AbortError');
  }

  // Allocate known-length storage before locking the stream so an allocation
  // failure can still cancel the response body cleanly.
  let knownLengthBuffer = null;
  if (declaredLength !== null) {
    try {
      knownLengthBuffer = new Uint8Array(declaredLength);
    } catch {
      await cancelResponseBody(response, 'Insufficient memory for model download.');
      throw new ModelDownloadError('memory', 'Not enough memory to buffer the model download.');
    }
  }
  const reader = response.body.getReader();
  // Unknown-length streams use a capped geometric buffer rather than retaining
  // every network chunk and then allocating a second full-size result.
  let unknownLengthBuffer = null;
  let total = 0;
  let abortHandler;
  try {
    if (signal) {
      abortHandler = () => { void reader.cancel('Model download aborted.').catch(() => {}); };
      signal.addEventListener('abort', abortHandler, { once: true });
    }
    while (true) {
      if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
      let part;
      try {
        part = await reader.read();
      } catch (error) {
        if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
        throw new ModelDownloadError('network', 'Model download stream failed.');
      }
      const { done, value } = part;
      if (done) break;
      if (!value) continue;
      const nextTotal = total + value.byteLength;
      if (nextTotal > MAX_MODEL_DOWNLOAD_BYTES) {
        await reader.cancel('Model exceeds the client download limit.').catch(() => {});
        throw new ModelDownloadError('too_large', 'Model exceeds the client download limit.');
      }
      if (declaredLength !== null && nextTotal > declaredLength) {
        await reader.cancel('Model response exceeded Content-Length.').catch(() => {});
        throw new ModelDownloadError('network', 'Model response exceeded its declared length.');
      }
      if (knownLengthBuffer) {
        knownLengthBuffer.set(value, total);
      } else {
        if (!unknownLengthBuffer || unknownLengthBuffer.byteLength < nextTotal) {
          const currentCapacity = unknownLengthBuffer?.byteLength ?? 0;
          const nextCapacity = Math.min(
            MAX_MODEL_DOWNLOAD_BYTES,
            Math.max(nextTotal, currentCapacity === 0 ? 64 * 1024 : currentCapacity * 2),
          );
          try {
            const grown = new Uint8Array(nextCapacity);
            if (unknownLengthBuffer) grown.set(unknownLengthBuffer.subarray(0, total));
            unknownLengthBuffer = grown;
          } catch {
            await reader.cancel('Insufficient memory for model download.').catch(() => {});
            throw new ModelDownloadError('memory', 'Not enough memory to buffer the model download.');
          }
        }
        unknownLengthBuffer.set(value, total);
      }
      total = nextTotal;
      if (declaredLength !== null && declaredLength > 0) {
        onProgress(Math.min(95, Math.floor((total / declaredLength) * 95)));
      }
    }
  } finally {
    if (signal && abortHandler) signal.removeEventListener('abort', abortHandler);
    try { reader.releaseLock(); } catch { /* stream may already be released */ }
  }
  if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
  if (declaredLength !== null && total !== declaredLength) {
    throw new ModelDownloadError('network', 'Model download length did not match the response header.');
  }
  if (knownLengthBuffer) return knownLengthBuffer.buffer;
  if (!unknownLengthBuffer || total === 0) return new ArrayBuffer(0);
  // Reuse the backing store when growth landed exactly on the final size.
  if (total === unknownLengthBuffer.byteLength) return unknownLengthBuffer.buffer;
  try {
    return unknownLengthBuffer.slice(0, total).buffer;
  } catch {
    // The stream has completed, but trimming the growth buffer still needs a
    // final exact-size allocation. Keep allocation failures on the same typed
    // recovery path as failures during streaming.
    throw new ModelDownloadError('memory', 'Not enough memory to finalize the model download buffer.');
  }
}

export function getHttpDownloadError(status) {
  if (status === 401) return new ModelDownloadError('unauthorized', 'Authentication required.', status);
  if (status === 403) return new ModelDownloadError('forbidden', 'Access denied.', status);
  if (status === 404) return new ModelDownloadError('not_found', 'Asset version not found.', status);
  if (status === 409) return new ModelDownloadError('conflict', 'Asset version state changed.', status);
  return new ModelDownloadError('http', 'Model download failed.', status);
}
