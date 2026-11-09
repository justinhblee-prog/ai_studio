import assert from 'node:assert/strict';
import { reportGltfParseError } from '../src/reportGltfParseError.mjs';

const message = 'parse failed';
const events = [];
const deps = {
  message,
  setErrorMessage: (value) => events.push(['message', value]),
  setLoadState: (value) => events.push(['state', value]),
  notifyError: (value) => events.push(['notify', value]),
};

assert.equal(reportGltfParseError({ ...deps, cancelled: true }), false);
assert.deepEqual(events, [], 'cancelled parse failures must not mutate state or notify');
assert.equal(reportGltfParseError({ ...deps, cancelled: false }), true);
assert.deepEqual(events, [['message', message], ['state', 'error'], ['notify', message]]);

const noConsumerEvents = [];
assert.equal(reportGltfParseError({
  cancelled: false, message,
  setErrorMessage: (value) => noConsumerEvents.push(['message', value]),
  setLoadState: (value) => noConsumerEvents.push(['state', value]),
}), true, 'notification callback is optional');
assert.deepEqual(noConsumerEvents, [['message', message], ['state', 'error']]);

let notifyCount = 0;
assert.equal(reportGltfParseError({
  cancelled: false, message,
  setErrorMessage() {}, setLoadState() {},
  notifyError: () => { notifyCount += 1; },
}), true);
assert.equal(notifyCount, 1, 'active request notifies exactly once');
console.log('GLTF parse error ownership: 8 assertions passed');
