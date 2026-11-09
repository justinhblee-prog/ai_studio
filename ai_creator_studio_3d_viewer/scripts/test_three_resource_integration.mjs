import assert from 'node:assert/strict';
let THREE;
try {
  THREE = await import('three');
} catch (error) {
  if (error?.code === 'ERR_MODULE_NOT_FOUND') {
    console.error('BLOCKED: Three.js resource integration requires the declared `three` dependency. Install project dependencies before running this test.');
  }
  throw error;
}
import { disposeGltfResources } from '../src/disposeGltfResources.mjs';

function countDisposeEvents(resource, label) {
  let count = 0;
  resource.addEventListener('dispose', () => { count += 1; });
  return { label, get count() { return count; } };
}

const sharedGeometry = new THREE.BufferGeometry();
sharedGeometry.setAttribute('position', new THREE.Float32BufferAttribute([
  0, 0, 0, 1, 0, 0, 0, 1, 0,
], 3));
const sharedTexture = new THREE.Texture();
const nestedTexture = new THREE.Texture();
const firstMaterial = new THREE.MeshStandardMaterial({ map: sharedTexture });
// GLTF extensions/custom shader integrations may retain textures in nested
// material metadata or uniform-like values; the disposer must walk these too.
firstMaterial.userData.auditUniforms = { nested: { value: [nestedTexture, sharedTexture] } };
const secondMaterial = new THREE.MeshStandardMaterial({ map: sharedTexture });

const bone = new THREE.Bone();
const skeleton = new THREE.Skeleton([bone]);
const firstScene = new THREE.Scene();
const secondScene = new THREE.Scene();
const meshA = new THREE.Mesh(sharedGeometry, firstMaterial);
const meshB = new THREE.Mesh(sharedGeometry, [firstMaterial, secondMaterial]);
const skinnedGeometry = new THREE.BufferGeometry();
const skinnedMesh = new THREE.SkinnedMesh(skinnedGeometry, secondMaterial);
skinnedMesh.add(bone);
skinnedMesh.bind(skeleton);
firstScene.add(meshA, meshB);
secondScene.add(skinnedMesh);

const observed = [
  countDisposeEvents(sharedGeometry, 'shared geometry'),
  countDisposeEvents(skinnedGeometry, 'skinned geometry'),
  countDisposeEvents(sharedTexture, 'shared texture'),
  countDisposeEvents(nestedTexture, 'nested texture'),
  countDisposeEvents(firstMaterial, 'first material'),
  countDisposeEvents(secondMaterial, 'second material'),
  countDisposeEvents(skeleton, 'skeleton'),
];

const result = disposeGltfResources({ scene: firstScene, scenes: [firstScene, secondScene] });
assert.deepEqual(result.errors, [], 'real Three.js resources should dispose without errors');
assert.deepEqual(result.counts, {
  textures: 2,
  materials: 2,
  geometries: 2,
  skeletons: 1,
});
for (const item of observed) {
  assert.equal(item.count, 1, `${item.label} emits exactly one dispose event`);
}

// Disposal remains idempotent even if separate lifecycle paths encounter the
// same graph. Three.js dispose events must not be emitted twice.
const repeat = disposeGltfResources({ scene: firstScene, scenes: [firstScene, secondScene] });
assert.deepEqual(repeat.errors, []);
assert.equal(repeat.attemptedCount, 0, 'previously attempted resources are skipped globally');
assert.ok(observed.every((item) => item.count === 1), 'a second pass does not re-emit dispose events');

console.log('Three.js resource integration: 13 assertions passed');
console.log(`Three.js revision: ${THREE.REVISION}`);
