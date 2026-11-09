/**
 * Bind WebGL context-loss/restoration events to the viewer's animation loop.
 * Three.js installs its own canvas listeners during WebGLRenderer construction;
 * this helper is attached afterwards so renderer restoration runs first.
 */
export function attachWebGLContextLifecycle({
  canvas,
  animationLoop,
  clock,
  resize = () => {},
  onLost = () => {},
  onRestored = () => {},
  onError = () => {},
}) {
  if (!canvas || typeof canvas.addEventListener !== 'function' || typeof canvas.removeEventListener !== 'function') {
    throw new TypeError('canvas must support addEventListener/removeEventListener');
  }
  if (!animationLoop || typeof animationLoop.stop !== 'function' || typeof animationLoop.start !== 'function') {
    throw new TypeError('animationLoop must support stop/start');
  }

  let lost = false;
  let disposed = false;
  let disposeRequested = false;
  let lifecycleGeneration = 0;
  let restoring = false;
  let lostListenerAttached = false;
  let restoredListenerAttached = false;

  const reportError = (error) => {
    try { onError(error); } catch { /* Diagnostics must never interrupt lifecycle cleanup. */ }
  };

  const handleLost = (event) => {
    if (disposed || disposeRequested || (lost && !restoring)) return;
    lost = true;
    lifecycleGeneration += 1;
    try { event?.preventDefault?.(); } catch { /* Continue stopping the render loop. */ }
    try { animationLoop.stop(); } catch (error) { reportError(error); }
    try { clock?.stop?.(); } catch (error) { reportError(error); }
    try { onLost(event); } catch (error) { reportError(error); }
  };

  const handleRestored = (event) => {
    if (disposed || disposeRequested || !lost || restoring) return;
    const recoveryGeneration = lifecycleGeneration;
    const recoveryStillOwned = () => (
      !disposed && !disposeRequested && lost && lifecycleGeneration === recoveryGeneration
    );
    restoring = true;
    try {
      clock?.start?.();
      if (!recoveryStillOwned()) return;
      resize();
      if (!recoveryStillOwned()) return;
      animationLoop.start();
      // Host callbacks can synchronously dispatch another context-loss event.
      // Never let an older restore operation overwrite that newer loss state.
      if (!recoveryStillOwned()) return;
      if (animationLoop.running === false) {
        throw new Error('animation loop did not resume after WebGL context restoration');
      }
      lost = false;
      onRestored(event);
    } catch (error) {
      reportError(error);
    } finally {
      restoring = false;
    }
  };

  canvas.addEventListener('webglcontextlost', handleLost, false);
  lostListenerAttached = true;
  try {
    canvas.addEventListener('webglcontextrestored', handleRestored, false);
    restoredListenerAttached = true;
  } catch (registrationError) {
    // Registration is transactional too: if the second listener cannot be
    // installed, retry removal of the first listener once. Some embedded
    // browser/event wrappers can fail transiently during teardown.
    const cleanupErrors = [];
    for (let attempt = 0; attempt < 2 && lostListenerAttached; attempt += 1) {
      try {
        canvas.removeEventListener('webglcontextlost', handleLost, false);
        lostListenerAttached = false;
      } catch (cleanupError) {
        cleanupErrors.push(cleanupError);
        reportError(cleanupError);
      }
    }
    if (lostListenerAttached) {
      const aggregate = new AggregateError(
        [registrationError, ...cleanupErrors],
        'WebGL context listener registration failed and rollback could not remove the loss listener',
      );
      throw aggregate;
    }
    throw registrationError;
  }

  return {
    dispose() {
      if (disposed) return true;
      // Once disposal starts, handlers become inert immediately. Keep retrying only
      // listeners whose removal failed so transient host errors cannot leak them.
      disposeRequested = true;
      lifecycleGeneration += 1;
      let removed = true;
      if (lostListenerAttached) {
        try { canvas.removeEventListener('webglcontextlost', handleLost, false); lostListenerAttached = false; }
        catch (error) { removed = false; reportError(error); }
      }
      if (restoredListenerAttached) {
        try { canvas.removeEventListener('webglcontextrestored', handleRestored, false); restoredListenerAttached = false; }
        catch (error) { removed = false; reportError(error); }
      }
      disposed = !lostListenerAttached && !restoredListenerAttached;
      return removed && disposed;
    },
    get lost() { return lost; },
    get disposed() { return disposed; },
  };
}

/**
 * Retry a partially failed listener teardown a bounded number of times.
 * Browser EventTarget removal is normally synchronous; the retry covers transient
 * host/test-wrapper failures without introducing timers or an unbounded cleanup loop.
 */
export function disposeWebGLContextLifecycleWithRetry(lifecycle, maxAttempts = 2) {
  if (!lifecycle || typeof lifecycle.dispose !== 'function') {
    throw new TypeError('lifecycle must provide dispose()');
  }
  if (!Number.isInteger(maxAttempts) || maxAttempts < 1 || maxAttempts > 5) {
    throw new RangeError('maxAttempts must be an integer from 1 to 5');
  }
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    if (lifecycle.dispose()) return true;
    if (lifecycle.disposed === true) return true;
  }
  return false;
}
