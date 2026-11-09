/** Own one requestAnimationFrame chain; stale callbacks cannot revive a stopped loop. */
export function createAnimationFrameController({ requestFrame, cancelFrame, render, onError = () => {} }) {
  if (typeof requestFrame !== 'function' || typeof cancelFrame !== 'function' || typeof render !== 'function') {
    throw new TypeError('requestFrame, cancelFrame and render must be functions');
  }

  let running = false;
  let frameId = null;
  let generation = 0;

  const report = (error) => {
    try { onError(error); } catch { /* Diagnostics must not break loop state. */ }
  };

  const tick = (ownedGeneration) => {
    if (!running || ownedGeneration !== generation) return;
    frameId = null;
    try {
      render();
    } catch (error) {
      if (ownedGeneration === generation) {
        running = false;
        generation += 1;
      }
      report(error);
      return;
    }

    // render() may synchronously stop and restart the controller. In that case
    // this callback no longer owns the loop and must not schedule a second chain.
    if (!running || ownedGeneration !== generation) return;
    try {
      frameId = requestFrame(() => tick(ownedGeneration));
    } catch (error) {
      if (ownedGeneration === generation) {
        running = false;
        frameId = null;
        generation += 1;
      }
      report(error);
    }
  };

  return {
    start() {
      if (running) return false;
      running = true;
      const ownedGeneration = ++generation;
      tick(ownedGeneration);
      return true;
    },
    stop() {
      const wasRunning = running || frameId !== null;
      running = false;
      generation += 1;
      if (frameId !== null) {
        const pending = frameId;
        frameId = null;
        cancelFrame(pending);
      }
      return wasRunning;
    },
    get running() { return running; },
    get pendingFrameId() { return frameId; },
  };
}
