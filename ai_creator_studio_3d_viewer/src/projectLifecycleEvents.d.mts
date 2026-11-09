export const PROJECT_LIFECYCLE_CHANGED: 'acs:project-lifecycle-changed';
export type ProjectLifecycleChange = { workspaceId: string; projectId: string };
export function publishProjectLifecycleChange(change: ProjectLifecycleChange): void;
export function subscribeProjectLifecycleChanges(listener: (change: ProjectLifecycleChange) => void): () => void;
