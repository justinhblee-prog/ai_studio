// Three.js dispose events are not intrinsically idempotent. Keep weak ownership
// state across disposal passes so a shared resource cannot be released twice
// when multiple lifecycle paths encounter the same object. WeakSet avoids
// retaining disposed GPU objects after their JS references become unreachable.
const globallyAttemptedResources = new WeakSet();

/**
 * Dispose GPU-backed resources created by GLTFLoader, including resources in
 * non-active scenes and nested material uniforms. Shared resources are attempted
 * exactly once per call. Failures are collected so one broken resource cannot
 * prevent cleanup of the remaining resources.
 */
export function disposeGltfResources(gltfOrScenes) {
  const scenes = Array.isArray(gltfOrScenes)
    ? gltfOrScenes
    : Array.isArray(gltfOrScenes?.scenes)
      ? gltfOrScenes.scenes
      : gltfOrScenes?.scene
        ? [gltfOrScenes.scene]
        : gltfOrScenes
          ? [gltfOrScenes]
          : [];

  const visitedValues = new WeakSet();
  const textures = new Set();
  const materials = new Set();
  const geometries = new Set();
  const skeletons = new Set();
  const errors = [];
  const counts = { textures: 0, materials: 0, geometries: 0, skeletons: 0 };
  let attemptedCount = 0;
  let disposedCount = 0;

  const describeError = (error) => {
    try {
      return error instanceof Error ? error.message : String(error);
    } catch {
      return 'Unprintable disposal error';
    }
  };
  const recordError = (stage, resourceType, error, resource) => {
    let resourceName;
    try {
      if (typeof resource?.name === 'string') resourceName = resource.name;
    } catch {
      // A diagnostic name is optional; never let a hostile getter break cleanup.
    }
    errors.push({ stage, resourceType, ...(resourceName ? { resourceName } : {}), message: describeError(error) });
  };

  const collectTextures = (value) => {
    if (!value || (typeof value !== 'object' && typeof value !== 'function')) return;
    let isTexture = false;
    try {
      isTexture = value.isTexture === true;
    } catch (error) {
      recordError('collect', 'material-value', error, value);
      return;
    }
    if (isTexture) {
      textures.add(value);
      return;
    }
    if (visitedValues.has(value)) return;
    visitedValues.add(value);
    if (Array.isArray(value)) {
      let length = 0;
      try { length = value.length; } catch (error) {
        recordError('collect', 'array', error, value);
        return;
      }
      for (let index = 0; index < length; index += 1) {
        try { collectTextures(value[index]); } catch (error) {
          recordError('collect', 'array-item', error, value);
        }
      }
      return;
    }
    let entries;
    try {
      entries = Object.keys(value);
    } catch (error) {
      recordError('collect', 'material-value', error, value);
      return;
    }
    for (const key of entries) {
      try { collectTextures(value[key]); } catch (error) {
        recordError('collect', 'material-property', error, value);
      }
    }
  };

  const disposeOnce = (resource, category) => {
    if (!resource || (typeof resource !== 'object' && typeof resource !== 'function')) return;
    if (globallyAttemptedResources.has(resource)) return;
    globallyAttemptedResources.add(resource);
    attemptedCount += 1;
    try {
      const dispose = resource.dispose;
      if (typeof dispose !== 'function') {
        recordError('dispose', ({ textures: 'texture', materials: 'material', geometries: 'geometry', skeletons: 'skeleton' })[category], new TypeError('dispose() is not a function'), resource);
        return;
      }
      dispose.call(resource);
      disposedCount += 1;
      counts[category] += 1;
    } catch (error) {
      recordError('dispose', ({ textures: 'texture', materials: 'material', geometries: 'geometry', skeletons: 'skeleton' })[category], error, resource);
    }
  };

  for (const scene of scenes) {
    if (!scene) continue;
    let traverse;
    try { traverse = scene.traverse; } catch (error) {
      recordError('traverse', 'scene', error, scene);
      continue;
    }
    if (typeof traverse !== 'function') continue;
    try {
      traverse.call(scene, (object) => {
        if (!object) return;
        try { if (object.geometry) geometries.add(object.geometry); } catch (error) {
          recordError('collect', 'geometry', error, object);
        }
        try { if (object.skeleton) skeletons.add(object.skeleton); } catch (error) {
          recordError('collect', 'skeleton', error, object);
        }
        let objectMaterials = [];
        try {
          const material = object.material;
          objectMaterials = Array.isArray(material) ? material : material ? [material] : [];
        } catch (error) {
          recordError('collect', 'material', error, object);
        }
        for (const material of objectMaterials) {
          if (!material || (typeof material !== 'object' && typeof material !== 'function')) continue;
          materials.add(material);
          collectTextures(material);
        }
      });
    } catch (error) {
      recordError('traverse', 'scene', error, scene);
    }
  }

  for (const texture of textures) disposeOnce(texture, 'textures');
  for (const material of materials) disposeOnce(material, 'materials');
  for (const geometry of geometries) disposeOnce(geometry, 'geometries');
  // Skeleton.dispose() releases its GPU bone texture when one was allocated.
  for (const skeleton of skeletons) disposeOnce(skeleton, 'skeletons');

  return { disposedCount, attemptedCount, counts, errors };
}
