/**
 * Guard the synchronous commit phase of an asynchronously parsed GLTF.
 * GLTFLoader.parse cannot be aborted once parsing starts, so stale results are
 * disposed immediately and commit-time exceptions must roll back any scene
 * attachment and GPU resources before the caller reports an error.
 */
export function finalizeGltfLoad({ gltf, cancelled = false, commit, rollback }) {
  const cleanup = (reason) => {
    try {
      rollback?.(gltf, reason);
      return null;
    } catch (cleanupError) {
      return cleanupError;
    }
  };

  if (cancelled) {
    const cleanupError = cleanup(new Error('GLTF load was cancelled before commit.'));
    return { status: 'cancelled', cleanupError };
  }

  try {
    commit(gltf);
    return { status: 'committed', cleanupError: null };
  } catch (error) {
    const cleanupError = cleanup(error);
    return { status: 'failed', error, cleanupError };
  }
}
