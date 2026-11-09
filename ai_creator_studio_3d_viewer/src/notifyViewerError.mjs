/** Notify an optional viewer error consumer without allowing it to break viewer recovery. */
export function notifyViewerError(callback, message) {
  if (typeof callback !== 'function') return false;
  try {
    callback(message);
    return true;
  } catch {
    // Consumer callbacks are outside the viewer's lifecycle and must not
    // interrupt error-state updates, request cancellation, or resource cleanup.
    return false;
  }
}
