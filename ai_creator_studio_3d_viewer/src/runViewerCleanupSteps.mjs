/** Run independent viewer teardown operations without aborting later cleanup. */
export function runViewerCleanupSteps(steps, onError = () => {}) {
  const errors = [];
  let completedCount = 0;
  let attemptedCount = 0;
  for (const step of Array.isArray(steps) ? steps : []) {
    if (!step || typeof step.run !== 'function') continue;
    attemptedCount += 1;
    try {
      step.run();
      completedCount += 1;
    } catch (error) {
      let message;
      try { message = error instanceof Error ? error.message : String(error); }
      catch { message = 'Unprintable cleanup error'; }
      errors.push({ name: typeof step.name === 'string' ? step.name : 'unnamed', message });
    }
  }
  const result = { attemptedCount, completedCount, errors };
  if (errors.length > 0) {
    try { onError(result); } catch { /* Diagnostics must never interrupt remaining teardown. */ }
  }
  return result;
}
