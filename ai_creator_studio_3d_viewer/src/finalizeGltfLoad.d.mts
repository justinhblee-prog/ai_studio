import type { GLTF } from 'three/addons/loaders/GLTFLoader.js';
export function finalizeGltfLoad(args: {
  gltf: GLTF;
  cancelled?: boolean;
  commit: (gltf: GLTF) => void;
  rollback?: (gltf: GLTF, reason?: unknown) => void;
}): { status: 'committed' | 'cancelled' | 'failed'; error?: unknown; cleanupError: unknown | null };
