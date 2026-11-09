import assert from 'node:assert/strict';
import { runViewerCleanupSteps } from '../src/runViewerCleanupSteps.mjs';

const order = [];
const result = runViewerCleanupSteps([
  { name: 'stop-loop', run: () => order.push('stop-loop') },
  { name: 'broken-controls', run: () => { order.push('broken-controls'); throw new Error('controls already disposed'); } },
  { name: 'release-gpu', run: () => order.push('release-gpu') },
  { name: 'clear-refs', run: () => order.push('clear-refs') },
]);
assert.deepEqual(order, ['stop-loop', 'broken-controls', 'release-gpu', 'clear-refs']);
assert.equal(result.attemptedCount, 4);
assert.equal(result.completedCount, 3);
assert.deepEqual(result.errors, [{ name: 'broken-controls', message: 'controls already disposed' }]);

let diagnosticResult = null;
const diagnosed = runViewerCleanupSteps([
  { name: 'broken-step', run: () => { throw new Error('diagnostic payload'); } },
  { name: 'later-step', run: () => order.push('later-step') },
], (value) => { diagnosticResult = value; });
assert.equal(diagnosticResult, diagnosed, 'cleanup errors are delivered to the diagnostic callback');
assert.deepEqual(diagnosticResult.errors, [{ name: 'broken-step', message: 'diagnostic payload' }]);
assert.ok(order.includes('later-step'), 'diagnostic callback runs after all cleanup steps');
assert.doesNotThrow(() => runViewerCleanupSteps([{ run: () => { throw new Error('ignored'); } }], () => { throw new Error('diagnostic sink failed'); }), 'diagnostic sink failures never interrupt cleanup');

const primitive = runViewerCleanupSteps([
  null,
  { name: 'not-callable', run: true },
  { name: 'throw-string', run: () => { throw 'failure'; } },
  { run: () => {} },
]);
assert.equal(primitive.attemptedCount, 2);
assert.equal(primitive.completedCount, 1);
assert.equal(primitive.errors.length, 1);
assert.equal(primitive.errors[0].message, 'failure');
console.log('Viewer cleanup runtime: 14 assertions passed');
