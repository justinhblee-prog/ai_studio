import assert from 'node:assert/strict';
import { createResourceRollback } from '../src/resourceRollback.mjs';

const events = [];
const transaction = createResourceRollback();
transaction.defer('renderer', () => events.push('renderer'));
transaction.defer('canvas', () => events.push('canvas'));
transaction.defer('controls', () => events.push('controls'));
const result = transaction.rollback();
assert.deepEqual(events, ['controls', 'canvas', 'renderer']);
assert.deepEqual(result, { attemptedCount: 3, completedCount: 3, errors: [] });
assert.equal(transaction.rollback().attemptedCount, 0);

const failures = [];
const isolated = createResourceRollback();
isolated.defer('first', () => failures.push('first'));
isolated.defer('broken', () => { throw new Error('injected disposer failure'); });
isolated.defer('last', () => failures.push('last'));
let diagnostic;
const failedResult = isolated.rollback((value) => { diagnostic = value; });
assert.deepEqual(failures, ['last', 'first']);
assert.equal(failedResult.attemptedCount, 3);
assert.equal(failedResult.completedCount, 2);
assert.deepEqual(failedResult.errors, [{ name: 'broken', message: 'injected disposer failure' }]);
assert.equal(diagnostic, failedResult);

const committed = createResourceRollback();
let committedDisposed = false;
committed.defer('resource', () => { committedDisposed = true; });
assert.equal(committed.commit(), true);
assert.equal(committed.rollback().attemptedCount, 0);
assert.equal(committedDisposed, false);

const transferred = createResourceRollback();
let transferredDisposals = 0;
const disposeTransferred = () => { transferredDisposals += 1; };
transferred.defer('transferable', disposeTransferred);
assert.equal(transferred.release(disposeTransferred), true);
assert.equal(transferred.release(disposeTransferred), false);
assert.equal(transferred.rollback().attemptedCount, 0);
assert.equal(transferredDisposals, 0);

assert.throws(() => committed.defer('late', () => {}), /already settled/);

// Failure-injection matrix: every acquisition boundary rolls back all prior resources.
for (let failAt = 0; failAt < 7; failAt += 1) {
  const acquired = [];
  const tx = createResourceRollback();
  let threw = false;
  try {
    for (let step = 0; step < 7; step += 1) {
      acquired.push(step);
      tx.defer(`resource-${step}`, () => acquired.push(`disposed-${step}`));
      if (step === failAt) throw new Error(`injected setup failure ${step}`);
    }
  } catch {
    threw = true;
    tx.rollback();
  }
  assert.equal(threw, true);
  assert.deepEqual(acquired.filter((item) => typeof item === 'string'), Array.from({ length: failAt + 1 }, (_, index) => `disposed-${failAt - index}`));
}

console.log('resource rollback tests: 17 assertions passed');

// Production wiring must register OrbitControls cleanup immediately after its
// constructor, because the constructor installs DOM listeners.
const { readFile } = await import('node:fs/promises');
const viewerSource = await readFile(new URL('../src/Studio3DViewer.tsx', import.meta.url), 'utf8');
const controlsCreate = viewerSource.indexOf('const controls = new OrbitControls(camera, renderer.domElement);');
const controlsDefer = viewerSource.indexOf("rollback.defer('dispose-orbit-controls', () => controls.dispose());", controlsCreate);
const controlsConfigure = viewerSource.indexOf('controls.enableDamping = true;', controlsCreate);
assert.ok(controlsCreate >= 0 && controlsDefer > controlsCreate, 'controls disposer is registered after construction');
assert.ok(controlsConfigure > controlsDefer, 'controls disposer is registered before configuration can fail');
console.log('OrbitControls immediate ownership registration: 2 assertions passed');
