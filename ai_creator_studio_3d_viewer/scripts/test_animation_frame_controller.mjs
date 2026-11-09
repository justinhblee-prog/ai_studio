import assert from 'node:assert/strict';
import { createAnimationFrameController } from '../src/animationFrameController.mjs';

let nextId = 1;
const pending = new Map();
const cancelled = [];
const requestFrame = (callback) => { const id = nextId++; pending.set(id, callback); return id; };
const cancelFrame = (id) => { cancelled.push(id); pending.delete(id); };
const fireNext = () => {
  const entry = pending.entries().next().value;
  assert.ok(entry, 'a frame should be pending');
  const [id, callback] = entry;
  pending.delete(id);
  callback(16);
};

let renders = 0;
const controller = createAnimationFrameController({ requestFrame, cancelFrame, render: () => { renders += 1; } });
assert.equal(controller.start(), true);
assert.equal(renders, 1, 'first frame renders immediately');
assert.equal(pending.size, 1, 'one frame is scheduled');
assert.equal(controller.start(), false, 'duplicate start is ignored');
fireNext();
assert.equal(renders, 2);
assert.equal(pending.size, 1, 'loop schedules exactly one successor');
const pendingId = controller.pendingFrameId;
assert.equal(controller.stop(), true);
assert.deepEqual(cancelled, [pendingId]);
assert.equal(pending.size, 0);
assert.equal(controller.stop(), false, 'stop is idempotent');
assert.equal(controller.running, false);

assert.equal(controller.start(), true, 'controller can restart');
assert.equal(renders, 3);
controller.stop();

let errors = 0;
const failing = createAnimationFrameController({
  requestFrame, cancelFrame,
  render: () => { throw new Error('synthetic render failure'); },
  onError: (error) => { assert.match(error.message, /synthetic render failure/); errors += 1; },
});
failing.start();
assert.equal(errors, 1);
assert.equal(failing.running, false, 'render failure stops the loop');
assert.equal(failing.pendingFrameId, null, 'render failure leaves no scheduled frame');
assert.equal(pending.size, 0);

let callbackError = 0;
const reportingFailure = createAnimationFrameController({
  requestFrame, cancelFrame, render: () => { throw new Error('render'); },
  onError: () => { callbackError += 1; throw new Error('reporting failed'); },
});
reportingFailure.start();
assert.equal(callbackError, 1);
assert.equal(reportingFailure.running, false, 'error callback failure does not revive loop');

// Scheduler failure after a successful render must leave no false-running state.
const scheduleError = new Error('requestAnimationFrame unavailable');
const scheduleErrors = [];
const scheduleFailure = createAnimationFrameController({
  requestFrame() { throw scheduleError; },
  cancelFrame() { throw new Error('no frame should exist to cancel'); },
  render() {},
  onError(error) { scheduleErrors.push(error); },
});
assert.equal(scheduleFailure.start(), true, 'start begins the initial render');
assert.equal(scheduleFailure.running, false, 'scheduler failure clears running state');
assert.equal(scheduleFailure.pendingFrameId, null, 'scheduler failure leaves no phantom frame');
assert.deepEqual(scheduleErrors, [scheduleError], 'scheduler failure is reported once');
assert.equal(scheduleFailure.stop(), false, 'stopping after scheduler failure is idempotent');

// A throwing diagnostic callback cannot leave the scheduler marked active.
const scheduleReportingFailure = createAnimationFrameController({
  requestFrame() { throw new Error('schedule'); },
  cancelFrame, render() {}, onError() { throw new Error('diagnostic'); },
});
scheduleReportingFailure.start();
assert.equal(scheduleReportingFailure.running, false, 'diagnostic failure does not mask scheduler shutdown');
assert.equal(scheduleReportingFailure.pendingFrameId, null);


// A render callback may synchronously stop/restart the loop. The old callback
// must not append a second RAF chain after the new generation has started.
let reentrantRenders = 0;
let reentrant;
reentrant = createAnimationFrameController({
  requestFrame, cancelFrame,
  render() {
    reentrantRenders += 1;
    if (reentrantRenders === 1) {
      reentrant.stop();
      reentrant.start();
    }
  },
});
assert.equal(reentrant.start(), true);
assert.equal(reentrantRenders, 2, 'restart inside render performs one fresh immediate render');
assert.equal(pending.size, 1, 'stale outer callback does not create a second RAF chain');
const onlyPendingId = reentrant.pendingFrameId;
reentrant.stop();
assert.equal(pending.size, 0);
assert.deepEqual(cancelled.at(-1), onlyPendingId);

// A callback already dequeued by the browser can still arrive after stop.
let staleCallback;
const staleController = createAnimationFrameController({
  requestFrame(callback) { staleCallback = callback; return 9001; },
  cancelFrame() {}, render() { renders += 1; },
});
staleController.start();
staleController.stop();
const rendersBeforeStale = renders;
staleCallback();
assert.equal(renders, rendersBeforeStale, 'stale callback after stop is ignored');
assert.equal(staleController.running, false);
assert.equal(staleController.pendingFrameId, null);

// A dequeued callback from an earlier generation must not interfere with a restart.
let oldGenerationCallback;
const generationPending = new Map();
let generationId = 1;
const generationController = createAnimationFrameController({
  requestFrame(callback) {
    const id = generationId++;
    generationPending.set(id, callback);
    if (id === 1) oldGenerationCallback = callback;
    return id;
  },
  cancelFrame(id) { generationPending.delete(id); },
  render() {},
});
generationController.start();
generationController.stop();
generationController.start();
const currentGenerationId = generationController.pendingFrameId;
const currentGenerationSize = generationPending.size;
oldGenerationCallback();
assert.equal(generationController.running, true, 'old callback cannot stop a newer generation');
assert.equal(generationController.pendingFrameId, currentGenerationId, 'old callback cannot overwrite the new frame id');
assert.equal(generationPending.size, currentGenerationSize, 'old callback cannot append another chain');
generationController.stop();

// Cancellation failures are reported by the caller, but stop state remains committed.
const cancelFailure = new Error('cancel failed');
const cancelFailureController = createAnimationFrameController({
  requestFrame(callback) { return callback; },
  cancelFrame() { throw cancelFailure; },
  render() {},
});
cancelFailureController.start();
assert.throws(() => cancelFailureController.stop(), cancelFailure);
assert.equal(cancelFailureController.running, false, 'cancel failure cannot leave the loop running');
assert.equal(cancelFailureController.pendingFrameId, null, 'cancel failure cannot leave a phantom frame id');
assert.equal(cancelFailureController.stop(), false, 'stop remains idempotent after cancellation failure');

// Error reporting may deliberately restart the controller; the failed generation
// must not overwrite or cancel the newly started generation.
let errorRestart;
let errorRestartCount = 0;
const errorRestartController = createAnimationFrameController({
  requestFrame(callback) { return requestFrame(callback); },
  cancelFrame,
  render() {
    errorRestartCount += 1;
    if (errorRestartCount === 1) throw new Error('first generation failed');
  },
  onError() { errorRestart.start(); },
});
errorRestart = errorRestartController;
assert.equal(errorRestartController.start(), true);
assert.equal(errorRestartCount, 2, 'error callback can start a fresh generation');
assert.equal(errorRestartController.running, true, 'old failure cannot overwrite restarted running state');
assert.equal(errorRestartController.pendingFrameId !== null, true, 'restarted generation owns its pending frame');
errorRestartController.stop();

console.log('Animation frame controller: 46 assertions passed');
