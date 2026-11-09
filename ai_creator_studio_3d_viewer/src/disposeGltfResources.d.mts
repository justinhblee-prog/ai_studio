export interface GltfDisposalError {
  stage: 'collect' | 'traverse' | 'dispose';
  resourceType: string;
  resourceName?: string;
  message: string;
}

export interface GltfDisposalResult {
  /** Number of resources whose disposal completed without throwing. */
  disposedCount: number;
  /** Number of unique resources for which disposal was attempted. */
  attemptedCount: number;
  counts: {
    textures: number;
    materials: number;
    geometries: number;
    skeletons: number;
  };
  /** Non-fatal collection, traversal, and disposal diagnostics. */
  errors: GltfDisposalError[];
}

export declare function disposeGltfResources(gltfOrScenes: unknown): GltfDisposalResult;
