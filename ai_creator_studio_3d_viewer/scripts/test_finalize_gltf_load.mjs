import assert from 'node:assert/strict';
import { finalizeGltfLoad } from '../src/finalizeGltfLoad.mjs';

const gltf = { scene: { name: 'fixture' } };
let commits = 0;
let rollbacks = 0;
const committed = finalizeGltfLoad({
  gltf,
  commit(value) { assert.equal(value, gltf); commits += 1; },
  rollback() { rollbacks += 1; },
});
assert.equal(committed.status, 'committed');
assert.equal(commits, 1);
assert.equal(rollbacks, 0);

const stale = finalizeGltfLoad({
  gltf,
  cancelled: true,
  commit() { assert.fail('cancelled GLTF must not commit'); },
  rollback(value) { assert.equal(value, gltf); rollbacks += 1; },
});
assert.equal(stale.status, 'cancelled');
assert.equal(stale.cleanupError, null);
assert.equal(rollbacks, 1);

const commitFailure = new Error('scene attachment failed');
const failed = finalizeGltfLoad({
  gltf,
  commit() { throw commitFailure; },
  rollback(value, reason) { assert.equal(value, gltf); assert.equal(reason, commitFailure); rollbacks += 1; },
});
assert.equal(failed.status, 'failed');
assert.equal(failed.error, commitFailure);
assert.equal(failed.cleanupError, null);
assert.equal(rollbacks, 2);

const cleanupFailure = new Error('GPU disposal failed');
const failedCleanup = finalizeGltfLoad({
  gltf,
  cancelled: true,
  commit() { assert.fail('cancelled GLTF must not commit'); },
  rollback() { throw cleanupFailure; },
});
assert.equal(failedCleanup.status, 'cancelled');
assert.equal(failedCleanup.cleanupError, cleanupFailure);

const failedCommitAndCleanup = finalizeGltfLoad({
  gltf,
  commit() { throw commitFailure; },
  rollback() { throw cleanupFailure; },
});
assert.equal(failedCommitAndCleanup.status, 'failed');
assert.equal(failedCommitAndCleanup.error, commitFailure);
assert.equal(failedCommitAndCleanup.cleanupError, cleanupFailure);
console.log('GLTF load commit lifecycle: 18 assertions passed');
