import assert from 'node:assert/strict';
import { disposeGltfResources } from '../src/disposeGltfResources.mjs';

function resource(name, extra = {}) {
  return { name, count: 0, dispose() { this.count += 1; }, ...extra };
}
function scene(objects) {
  return { traverse(callback) { for (const object of objects) callback(object); } };
}

const sharedTexture = resource('shared texture', { isTexture: true });
const nestedTexture = resource('nested texture', { isTexture: true });
const firstMaterial = resource('first material', { map: sharedTexture });
const secondMaterial = resource('second material', {
  uniforms: { diffuse: { value: [nestedTexture, { nested: sharedTexture }] } },
});
const sharedGeometry = resource('shared geometry');
const unusedSceneGeometry = resource('unused scene geometry');
const firstScene = scene([
  { geometry: sharedGeometry, material: firstMaterial },
  { geometry: sharedGeometry, material: [firstMaterial, secondMaterial] },
]);
const secondScene = scene([{ geometry: unusedSceneGeometry, material: secondMaterial }]);

disposeGltfResources({ scene: firstScene, scenes: [firstScene, secondScene] });
for (const item of [sharedTexture, nestedTexture, firstMaterial, secondMaterial, sharedGeometry, unusedSceneGeometry]) {
  assert.equal(item.count, 1, `${item.name} should be disposed once`);
}

const legacyTexture = resource('legacy texture', { isTexture: true });
const legacyMaterial = resource('legacy material', { map: legacyTexture });
const legacyGeometry = resource('legacy geometry');
disposeGltfResources(scene([{ geometry: legacyGeometry, material: legacyMaterial }]));
assert.equal(legacyTexture.count, 1);
assert.equal(legacyMaterial.count, 1);
assert.equal(legacyGeometry.count, 1);

disposeGltfResources(null);
disposeGltfResources({ scenes: [] });
console.log('GLTF disposal tests: 9 assertions passed');

const cyclicTexture = resource('cyclic texture', { isTexture: true });
const cyclicMaterial = resource('cyclic material');
const cycle = { nested: cyclicTexture };
cycle.self = cycle;
cyclicMaterial.uniforms = { value: cycle };
disposeGltfResources(scene([{ material: cyclicMaterial }]));
assert.equal(cyclicTexture.count, 1);
assert.equal(cyclicMaterial.count, 1);
console.log('GLTF disposal cycle guard: 2 assertions passed');

const sharedSkeleton = resource('shared skeleton');
const firstSkinnedGeometry = resource('first skinned geometry');
const secondSkinnedGeometry = resource('second skinned geometry');
const skinnedScene = scene([
  { geometry: firstSkinnedGeometry, skeleton: sharedSkeleton },
  { geometry: secondSkinnedGeometry, skeleton: sharedSkeleton },
]);
disposeGltfResources(skinnedScene);
assert.equal(sharedSkeleton.count, 1, 'shared skeleton should be disposed once');
assert.equal(firstSkinnedGeometry.count, 1);
assert.equal(secondSkinnedGeometry.count, 1);
console.log('GLTF skeleton disposal: 3 assertions passed');

// Best-effort behavior: a failing resource is reported, while later resources
// and duplicate references are still handled exactly once.
const failingTexture = resource('failing texture', {
  isTexture: true,
  dispose() { this.count += 1; throw new Error('texture dispose failed'); },
});
const laterTexture = resource('later texture', { isTexture: true });
const bestEffortMaterial = resource('best effort material', {
  map: failingTexture,
  normalMap: laterTexture,
});
const bestEffortGeometry = resource('best effort geometry');
const bestEffortSkeleton = resource('best effort skeleton');
const bestEffortResult = disposeGltfResources(scene([
  { geometry: bestEffortGeometry, material: bestEffortMaterial, skeleton: bestEffortSkeleton },
  { geometry: bestEffortGeometry, material: bestEffortMaterial, skeleton: bestEffortSkeleton },
]));
assert.equal(failingTexture.count, 1, 'failing shared texture should only be attempted once');
assert.equal(laterTexture.count, 1, 'later texture should still be disposed');
assert.equal(bestEffortMaterial.count, 1, 'material should still be disposed');
assert.equal(bestEffortGeometry.count, 1, 'shared geometry should still be disposed once');
assert.equal(bestEffortSkeleton.count, 1, 'shared skeleton should still be disposed once');
assert.equal(bestEffortResult.attemptedCount, 5);
assert.equal(bestEffortResult.disposedCount, 4);
assert.deepEqual(bestEffortResult.counts, { textures: 1, materials: 1, geometries: 1, skeletons: 1 });
assert.equal(bestEffortResult.errors.length, 1);
assert.equal(bestEffortResult.errors[0].stage, 'dispose');
assert.equal(bestEffortResult.errors[0].resourceType, 'texture');
assert.equal(bestEffortResult.errors[0].resourceName, 'failing texture');
assert.match(bestEffortResult.errors[0].message, /texture dispose failed/);
console.log('GLTF best-effort disposal: 10 assertions passed');

// A traversal failure is diagnostic and does not block subsequent scenes.
const afterTraversalFailure = resource('after traversal failure');
const brokenScene = { traverse() { throw new Error('scene traversal failed'); } };
const traversalResult = disposeGltfResources([brokenScene, scene([{ geometry: afterTraversalFailure }])]);
assert.equal(afterTraversalFailure.count, 1);
assert.equal(traversalResult.disposedCount, 1);
assert.equal(traversalResult.errors.length, 1);
assert.equal(traversalResult.errors[0].stage, 'traverse');
assert.match(traversalResult.errors[0].message, /scene traversal failed/);
console.log('GLTF traversal failure isolation: 5 assertions passed');

// A throwing nested-property getter is reported without suppressing other
// discoverable resources or the material/geometry disposal passes.
const getterSafeTexture = resource('getter-safe texture', { isTexture: true });
const getterSafeMaterial = resource('getter-safe material');
Object.defineProperty(getterSafeMaterial, 'brokenUniform', {
  enumerable: true,
  get() { throw new Error('uniform getter failed'); },
});
getterSafeMaterial.goodUniform = getterSafeTexture;
const getterResult = disposeGltfResources(scene([{ material: getterSafeMaterial }]));
assert.equal(getterSafeTexture.count, 1);
assert.equal(getterSafeMaterial.count, 1);
assert.equal(getterResult.errors.length, 1);
assert.equal(getterResult.errors[0].stage, 'collect');
assert.match(getterResult.errors[0].message, /uniform getter failed/);
console.log('GLTF collection failure isolation: 4 assertions passed');

// Cross-pass ownership guard: distinct teardown paths may encounter the same
// Three.js object. Its dispose() method must be attempted only once globally.
const crossPassGeometry = resource('cross-pass geometry');
const crossPassScene = scene([{ geometry: crossPassGeometry }]);
const firstPass = disposeGltfResources(crossPassScene);
const secondPass = disposeGltfResources(crossPassScene);
assert.equal(firstPass.attemptedCount, 1);
assert.equal(secondPass.attemptedCount, 0);
assert.equal(crossPassGeometry.count, 1, 'cross-pass resource is disposed once');
console.log('GLTF cross-pass idempotency: 3 assertions passed');


// A throwing dispose() is still considered attempted and is not retried by a
// later teardown pass. This avoids repeated side effects from partially-failed
// GPU cleanup; diagnostics are returned to the caller on the first pass.
const crossPassFailingTexture = resource('cross-pass failing texture', {
  isTexture: true,
  dispose() { this.count += 1; throw new Error('cross-pass release failed'); },
});
const crossPassFailingScene = scene([{ material: resource('cross-pass failing material', { map: crossPassFailingTexture }) }]);
const failedFirstPass = disposeGltfResources(crossPassFailingScene);
const failedSecondPass = disposeGltfResources(crossPassFailingScene);
assert.equal(failedFirstPass.errors.length, 1);
assert.equal(failedFirstPass.attemptedCount, 2);
assert.equal(failedSecondPass.errors.length, 0);
assert.equal(failedSecondPass.attemptedCount, 0);
assert.equal(crossPassFailingTexture.count, 1, 'a failed dispose is not invoked again on later passes');
console.log('GLTF failed-dispose cross-pass policy: 5 assertions passed');
