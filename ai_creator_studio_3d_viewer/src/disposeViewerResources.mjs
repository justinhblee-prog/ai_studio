import { disposeGltfResources } from './disposeGltfResources.mjs';

/**
 * Dispose a viewer-owned GLTF/scene resource graph and surface diagnostics to
 * the surrounding failure-isolated lifecycle runner after all releases were
 * attempted. This keeps teardown best-effort without silently losing errors.
 */
export function disposeViewerResources(resources) {
  const result = disposeGltfResources(resources);
  if (result.errors.length > 0) {
    const first = result.errors[0];
    const detail = `${first.stage}/${first.resourceType}: ${first.message}`;
    throw new Error(`Viewer resource disposal reported ${result.errors.length} error(s); ${detail}`);
  }
  return result;
}
