/**
 * Transactional disposer stack for resources acquired during viewer setup.
 * Register each disposer immediately after acquiring its resource. If setup
 * fails, rollback runs in reverse acquisition order and isolates failures.
 */
export function createResourceRollback() {
  const disposers = [];
  let settled = false;

  return {
    defer(name, dispose) {
      if (settled) throw new Error('resource rollback transaction is already settled');
      if (typeof dispose !== 'function') throw new TypeError('resource disposer must be a function');
      disposers.push({ name: typeof name === 'string' && name ? name : 'unnamed', dispose });
      return dispose;
    },
    release(dispose) {
      if (settled) return false;
      const index = disposers.findIndex((entry) => entry.dispose === dispose);
      if (index < 0) return false;
      disposers.splice(index, 1);
      return true;
    },
    commit() {
      if (settled) return false;
      settled = true;
      disposers.length = 0;
      return true;
    },
    rollback(onError = () => {}) {
      if (settled) return { attemptedCount: 0, completedCount: 0, errors: [] };
      settled = true;
      const errors = [];
      let completedCount = 0;
      const pending = disposers.splice(0).reverse();
      for (const entry of pending) {
        try {
          entry.dispose();
          completedCount += 1;
        } catch (error) {
          let message;
          try { message = error instanceof Error ? error.message : String(error); }
          catch { message = 'Unprintable cleanup error'; }
          errors.push({ name: entry.name, message });
        }
      }
      const result = { attemptedCount: pending.length, completedCount, errors };
      if (errors.length) {
        try { onError(result); } catch { /* Rollback diagnostics are best-effort. */ }
      }
      return result;
    },
    get settled() { return settled; },
    get pendingCount() { return disposers.length; },
  };
}
