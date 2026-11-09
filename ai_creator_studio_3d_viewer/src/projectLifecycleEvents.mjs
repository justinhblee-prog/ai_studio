/** Same-tab notification for project lifecycle changes across workspace panels. */
export const PROJECT_LIFECYCLE_CHANGED = 'acs:project-lifecycle-changed';

export function publishProjectLifecycleChange(change) {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent(PROJECT_LIFECYCLE_CHANGED, { detail: change }));
}

export function subscribeProjectLifecycleChanges(listener) {
  if (typeof window === 'undefined') return () => undefined;
  const handler = (event) => {
    const detail = event?.detail;
    if (detail && typeof detail.workspaceId === 'string' && typeof detail.projectId === 'string') listener(detail);
  };
  window.addEventListener(PROJECT_LIFECYCLE_CHANGED, handler);
  return () => window.removeEventListener(PROJECT_LIFECYCLE_CHANGED, handler);
}
