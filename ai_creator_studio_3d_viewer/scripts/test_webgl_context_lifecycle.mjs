import assert from 'node:assert/strict';
import { attachWebGLContextLifecycle, disposeWebGLContextLifecycleWithRetry } from '../src/webglContextLifecycle.mjs';

class FakeCanvas {
  listeners = new Map();
  addEventListener(type, handler) {
    const handlers = this.listeners.get(type) ?? new Set();
    handlers.add(handler);
    this.listeners.set(type, handlers);
  }
  removeEventListener(type, handler) { this.listeners.get(type)?.delete(handler); }
  dispatch(type) {
    let prevented = false;
    for (const handler of this.listeners.get(type) ?? []) {
      handler({ preventDefault() { prevented = true; } });
    }
    return prevented;
  }
}

const canvas = new FakeCanvas();
const calls = { starts: 0, stops: 0, clockStarts: 0, clockStops: 0, resizes: 0, lost: 0, restored: 0, errors: [] };
const animationLoop = {
  start() { calls.starts += 1; return true; },
  stop() { calls.stops += 1; return true; },
};
const clock = {
  start() { calls.clockStarts += 1; },
  stop() { calls.clockStops += 1; },
};
const lifecycle = attachWebGLContextLifecycle({
  canvas, animationLoop, clock,
  resize() { calls.resizes += 1; },
  onLost() { calls.lost += 1; },
  onRestored() { calls.restored += 1; },
  onError(error) { calls.errors.push(error); },
});

assert.equal(canvas.dispatch('webglcontextlost'), true, 'context loss must be prevented by default');
assert.equal(lifecycle.lost, true);
assert.equal(calls.stops, 1, 'render loop stops on loss');
assert.equal(calls.clockStops, 1, 'clock stops on loss');
assert.equal(calls.lost, 1);
canvas.dispatch('webglcontextlost');
assert.equal(calls.stops, 1, 'duplicate loss events are ignored');
assert.equal(calls.lost, 1);

canvas.dispatch('webglcontextrestored');
assert.equal(lifecycle.lost, false);
assert.equal(calls.clockStarts, 1, 'clock restarts after restoration');
assert.equal(calls.resizes, 1, 'viewport is resized after restoration');
assert.equal(calls.starts, 1, 'render loop restarts after restoration');
assert.equal(calls.restored, 1);
canvas.dispatch('webglcontextrestored');
assert.equal(calls.starts, 1, 'spurious restore events are ignored');

assert.equal(lifecycle.dispose(), true);
assert.equal(lifecycle.dispose(), true, 'completed listener disposal is idempotent');
assert.equal(lifecycle.disposed, true);
canvas.dispatch('webglcontextlost');
assert.equal(calls.stops, 1, 'removed listeners do not process later events');
assert.deepEqual(calls.errors, []);
console.log('WebGL context lifecycle: 15 assertions passed');

// A failed viewport restoration must not falsely report the context as restored.
const retryCanvas = new FakeCanvas();
let resizeAttempts = 0;
let restartAttempts = 0;
const retryErrors = [];
const retry = attachWebGLContextLifecycle({
  canvas: retryCanvas,
  animationLoop: { stop() {}, start() { restartAttempts += 1; } },
  resize() { resizeAttempts += 1; if (resizeAttempts === 1) throw new Error('resize failed'); },
  onError(error) { retryErrors.push(error.message); },
});
retryCanvas.dispatch('webglcontextlost');
retryCanvas.dispatch('webglcontextrestored');
assert.equal(retry.lost, true, 'failed restoration remains in lost state');
assert.equal(restartAttempts, 0, 'render loop is not restarted after failed resize');
retryCanvas.dispatch('webglcontextrestored');
assert.equal(retry.lost, false, 'a later restore event can retry recovery');
assert.equal(restartAttempts, 1);
assert.deepEqual(retryErrors, ['resize failed']);
retry.dispose();
console.log('WebGL context restoration retry: 5 assertions passed');

// Guard the production component wiring and teardown order as well as the helper.
const { readFile } = await import('node:fs/promises');
const viewerSource = await readFile(new URL('../src/Studio3DViewer.tsx', import.meta.url), 'utf8');
assert.match(viewerSource, /attachWebGLContextLifecycle\(/, 'Viewer wires context lifecycle helper');
assert.match(viewerSource, /onLost: \(\) => setContextLost\(true\)/, 'Viewer surfaces context loss');
assert.match(viewerSource, /onRestored: \(\) => setContextLost\(false\)/, 'Viewer clears context-loss state after recovery');
assert.match(viewerSource, /name: 'remove-webgl-context-listeners'[\s\S]*?disposeWebGLContextLifecycleWithRetry\(contextLifecycle, 2\)/, 'Viewer retries transient context-listener teardown failures');
assert.match(viewerSource, /name: 'cancel-animation-frame'[\s\S]*?name: 'remove-webgl-context-listeners'/, 'render loop is stopped before listeners are removed');
console.log('WebGL Viewer integration contract: 5 assertions passed');

// A controller that fails its immediate restoration render must not be marked healthy.
const renderFailureCanvas = new FakeCanvas();
let controllerRunning = true;
let renderFailureCount = 0;
const renderFailure = attachWebGLContextLifecycle({
  canvas: renderFailureCanvas,
  animationLoop: {
    get running() { return controllerRunning; },
    stop() { controllerRunning = false; },
    start() { controllerRunning = false; },
  },
  onError(error) { renderFailureCount += 1; assert.match(error.message, /did not resume/); },
});
renderFailureCanvas.dispatch('webglcontextlost');
renderFailureCanvas.dispatch('webglcontextrestored');
assert.equal(renderFailure.lost, true, 'failed first render leaves context lifecycle in lost state');
assert.equal(renderFailureCount, 1, 'failed loop restart is reported');
renderFailure.dispose();
console.log('WebGL render-loop restart failure: 2 assertions passed');

// Failure to stop the loop must not skip clock stop or the loss notification.
const stopFailureCanvas = new FakeCanvas();
const stopFailureEvents = [];
const stopFailure = attachWebGLContextLifecycle({
  canvas: stopFailureCanvas,
  animationLoop: { stop() { throw new Error('stop failed'); }, start() {} },
  clock: { stop() { stopFailureEvents.push('clock-stop'); } },
  onLost() { stopFailureEvents.push('lost-callback'); },
  onError(error) { stopFailureEvents.push(`error:${error.message}`); },
});
stopFailureCanvas.dispatch('webglcontextlost');
assert.deepEqual(stopFailureEvents, ['error:stop failed', 'clock-stop', 'lost-callback']);
assert.equal(stopFailure.lost, true);
stopFailure.dispose();
console.log('WebGL loss-handler failure isolation: 4 assertions passed');

// Listener registration is transactional: roll back the first listener if the second fails.
const registrationEvents = [];
const registrationCanvas = {
  addEventListener(type) { registrationEvents.push(`add:${type}`); if (type === 'webglcontextrestored') throw new Error('restore listener failed'); },
  removeEventListener(type) { registrationEvents.push(`remove:${type}`); },
};
assert.throws(() => attachWebGLContextLifecycle({ canvas: registrationCanvas, animationLoop: { stop() {}, start() {} } }), /restore listener failed/);
assert.deepEqual(registrationEvents, ['add:webglcontextlost', 'add:webglcontextrestored', 'remove:webglcontextlost']);
console.log('WebGL listener registration rollback: 2 assertions passed');

// Listener removal attempts both handlers even when one removal throws.
const removalEvents = [];
const removalErrors = [];
const removalCanvas = {
  addEventListener(type) { removalEvents.push(`add:${type}`); },
  removeEventListener(type) { removalEvents.push(`remove:${type}`); if (type === 'webglcontextlost') throw new Error('lost listener removal failed'); },
};
const removalLifecycle = attachWebGLContextLifecycle({
  canvas: removalCanvas,
  animationLoop: { stop() {}, start() {} },
  onError(error) { removalErrors.push(error.message); },
});
assert.equal(removalLifecycle.dispose(), false, 'partial listener removal is reported');
assert.deepEqual(removalEvents, ['add:webglcontextlost', 'add:webglcontextrestored', 'remove:webglcontextlost', 'remove:webglcontextrestored']);
assert.deepEqual(removalErrors, ['lost listener removal failed']);
assert.equal(removalLifecycle.disposed, false, 'partial listener removal does not claim full disposal');
assert.equal(removalLifecycle.dispose(), false, 'a still-failing listener remains pending removal');
console.log('WebGL listener teardown failure isolation: 6 assertions passed');

// A transient removal failure can be retried without re-removing the listener already detached.
const transientRemovalEvents = [];
let failFirstLostRemoval = true;
const transientRemovalCanvas = {
  addEventListener(type) { transientRemovalEvents.push(`add:${type}`); },
  removeEventListener(type) {
    transientRemovalEvents.push(`remove:${type}`);
    if (type === 'webglcontextlost' && failFirstLostRemoval) { failFirstLostRemoval = false; throw new Error('temporary remove failure'); }
  },
};
const transientRemoval = attachWebGLContextLifecycle({
  canvas: transientRemovalCanvas,
  animationLoop: { stop() {}, start() {} },
});
assert.equal(transientRemoval.dispose(), false, 'first disposal reports transient removal failure');
assert.equal(transientRemoval.disposed, false, 'failed listener keeps disposal pending');
assert.equal(transientRemoval.dispose(), true, 'second disposal completes after transient failure');
assert.equal(transientRemoval.disposed, true);
assert.deepEqual(transientRemovalEvents, [
  'add:webglcontextlost', 'add:webglcontextrestored',
  'remove:webglcontextlost', 'remove:webglcontextrestored', 'remove:webglcontextlost',
]);
transientRemovalCanvas && assert.equal(transientRemoval.dispose(), true, 'completed disposal is idempotent');
console.log('WebGL transient listener removal retry: 6 assertions passed');

// Production teardown uses a bounded retry, so a transient removeEventListener failure
// does not leave the canvas listener attached after React's one-shot effect cleanup.
const boundedRetryEvents = [];
let boundedRetryFailures = 1;
const boundedRetryCanvas = {
  addEventListener(type) { boundedRetryEvents.push(`add:${type}`); },
  removeEventListener(type) {
    boundedRetryEvents.push(`remove:${type}`);
    if (type === 'webglcontextlost' && boundedRetryFailures > 0) {
      boundedRetryFailures -= 1;
      throw new Error('temporary host removal failure');
    }
  },
};
const boundedRetryLifecycle = attachWebGLContextLifecycle({
  canvas: boundedRetryCanvas, animationLoop: { stop() {}, start() {} },
});
assert.equal(disposeWebGLContextLifecycleWithRetry(boundedRetryLifecycle, 2), true, 'bounded teardown retry completes transient failure');
assert.equal(boundedRetryLifecycle.disposed, true);
assert.equal(boundedRetryEvents.filter((event) => event === 'remove:webglcontextrestored').length, 1, 'already removed listener is not removed twice');
assert.equal(boundedRetryEvents.filter((event) => event === 'remove:webglcontextlost').length, 2, 'only failed listener is retried');
assert.equal(disposeWebGLContextLifecycleWithRetry(boundedRetryLifecycle, 2), true, 'completed teardown remains idempotent');

let persistentAttempts = 0;
const persistentLifecycle = { dispose() { persistentAttempts += 1; return false; }, disposed: false };
assert.equal(disposeWebGLContextLifecycleWithRetry(persistentLifecycle, 3), false, 'persistent failure returns false');
assert.equal(persistentAttempts, 3, 'retry count is strictly bounded');
assert.throws(() => disposeWebGLContextLifecycleWithRetry(persistentLifecycle, 0), /maxAttempts/);
assert.throws(() => disposeWebGLContextLifecycleWithRetry(persistentLifecycle, 6), /maxAttempts/);
console.log('WebGL bounded component teardown retry: 8 assertions passed');


// A transient failure while rolling back a partially registered listener is retried.
const registrationRetryEvents = [];
let failRegistrationRollbackOnce = true;
const registrationRetryCanvas = {
  addEventListener(type) {
    registrationRetryEvents.push(`add:${type}`);
    if (type === 'webglcontextrestored') throw new Error('restore registration failed');
  },
  removeEventListener(type) {
    registrationRetryEvents.push(`remove:${type}`);
    if (type === 'webglcontextlost' && failRegistrationRollbackOnce) {
      failRegistrationRollbackOnce = false;
      throw new Error('temporary rollback removal failure');
    }
  },
};
assert.throws(() => attachWebGLContextLifecycle({ canvas: registrationRetryCanvas, animationLoop: { stop() {}, start() {} } }), /restore registration failed/);
assert.deepEqual(registrationRetryEvents, [
  'add:webglcontextlost', 'add:webglcontextrestored',
  'remove:webglcontextlost', 'remove:webglcontextlost',
]);
console.log('WebGL partial registration rollback retry: 2 assertions passed');

// Persistent rollback failure is surfaced together with the original registration error.
let persistentRegistrationRemovals = 0;
const persistentRegistrationCanvas = {
  addEventListener(type) { if (type === 'webglcontextrestored') throw new Error('restore registration failed'); },
  removeEventListener() { persistentRegistrationRemovals += 1; throw new Error('listener removal permanently blocked'); },
};
assert.throws(
  () => attachWebGLContextLifecycle({ canvas: persistentRegistrationCanvas, animationLoop: { stop() {}, start() {} } }),
  (error) => error instanceof AggregateError && error.errors.length === 3 && /rollback could not remove/.test(error.message),
);
assert.equal(persistentRegistrationRemovals, 2, 'partial registration rollback attempts are bounded');
console.log('WebGL persistent registration rollback failure reporting: 2 assertions passed');

// Reentrant context loss during resize must abort the stale restoration transaction.
const resizeLossCanvas = new FakeCanvas();
let resizeLossStarts = 0;
let resizeLossRestored = 0;
const resizeLossLifecycle = attachWebGLContextLifecycle({
  canvas: resizeLossCanvas,
  animationLoop: { stop() {}, start() { resizeLossStarts += 1; } },
  resize() { resizeLossCanvas.dispatch('webglcontextlost'); },
  onRestored() { resizeLossRestored += 1; },
});
resizeLossCanvas.dispatch('webglcontextlost');
resizeLossCanvas.dispatch('webglcontextrestored');
assert.equal(resizeLossLifecycle.lost, true, 'reentrant loss during resize remains authoritative');
assert.equal(resizeLossStarts, 0, 'stale restore does not restart after reentrant loss');
assert.equal(resizeLossRestored, 0, 'stale restore does not emit restored callback');
resizeLossLifecycle.dispose();
console.log('WebGL reentrant loss during resize: 3 assertions passed');

// Reentrant loss from animationLoop.start must not be overwritten by restore completion.
const startLossCanvas = new FakeCanvas();
let startLossRestored = 0;
const startLossLifecycle = attachWebGLContextLifecycle({
  canvas: startLossCanvas,
  animationLoop: {
    stop() {},
    start() { startLossCanvas.dispatch('webglcontextlost'); },
  },
  onRestored() { startLossRestored += 1; },
});
startLossCanvas.dispatch('webglcontextlost');
startLossCanvas.dispatch('webglcontextrestored');
assert.equal(startLossLifecycle.lost, true, 'loss during loop restart is not cleared by stale restore');
assert.equal(startLossRestored, 0, 'restored callback is suppressed after reentrant loss');
startLossLifecycle.dispose();
console.log('WebGL reentrant loss during loop restart: 2 assertions passed');

// A duplicate restore event dispatched from resize is ignored while recovery is active.
const duplicateRestoreCanvas = new FakeCanvas();
let duplicateRestoreStarts = 0;
let duplicateRestoreCallbacks = 0;
const duplicateRestoreLifecycle = attachWebGLContextLifecycle({
  canvas: duplicateRestoreCanvas,
  animationLoop: { stop() {}, start() { duplicateRestoreStarts += 1; } },
  resize() { duplicateRestoreCanvas.dispatch('webglcontextrestored'); },
  onRestored() { duplicateRestoreCallbacks += 1; },
});
duplicateRestoreCanvas.dispatch('webglcontextlost');
duplicateRestoreCanvas.dispatch('webglcontextrestored');
assert.equal(duplicateRestoreStarts, 1, 'nested restore event does not start a second loop');
assert.equal(duplicateRestoreCallbacks, 1, 'nested restore event does not duplicate restored callback');
assert.equal(duplicateRestoreLifecycle.lost, false);
duplicateRestoreLifecycle.dispose();
console.log('WebGL duplicate restore reentrancy: 3 assertions passed');

// A new context loss dispatched by the restored callback starts a fresh loss
// generation; the completed recovery must not erase that newer state.
const callbackLossCanvas = new FakeCanvas();
let callbackLossStops = 0;
let callbackLossRestored = 0;
const callbackLossLifecycle = attachWebGLContextLifecycle({
  canvas: callbackLossCanvas,
  animationLoop: {
    stop() { callbackLossStops += 1; },
    start() {},
  },
  onRestored() {
    callbackLossRestored += 1;
    callbackLossCanvas.dispatch('webglcontextlost');
  },
});
callbackLossCanvas.dispatch('webglcontextlost');
callbackLossCanvas.dispatch('webglcontextrestored');
assert.equal(callbackLossRestored, 1, 'restore callback runs once before a new loss');
assert.equal(callbackLossStops, 2, 'new loss from restored callback stops the restarted loop');
assert.equal(callbackLossLifecycle.lost, true, 'new loss from restored callback remains authoritative');
callbackLossLifecycle.dispose();
console.log('WebGL reentrant loss from restored callback: 3 assertions passed');

// Clock startup is also a host callback boundary and may synchronously signal
// another context loss; resize and animation restart must then be skipped.
const clockLossCanvas = new FakeCanvas();
let clockLossResizes = 0;
let clockLossStarts = 0;
const clockLossLifecycle = attachWebGLContextLifecycle({
  canvas: clockLossCanvas,
  animationLoop: { stop() {}, start() { clockLossStarts += 1; } },
  clock: { start() { clockLossCanvas.dispatch('webglcontextlost'); }, stop() {} },
  resize() { clockLossResizes += 1; },
});
clockLossCanvas.dispatch('webglcontextlost');
clockLossCanvas.dispatch('webglcontextrestored');
assert.equal(clockLossLifecycle.lost, true, 'clock-start reentrant loss remains authoritative');
assert.equal(clockLossResizes, 0, 'resize is skipped after clock-start reentrant loss');
assert.equal(clockLossStarts, 0, 'animation loop is not restarted after clock-start reentrant loss');
clockLossLifecycle.dispose();
console.log('WebGL reentrant loss during clock startup: 3 assertions passed');
