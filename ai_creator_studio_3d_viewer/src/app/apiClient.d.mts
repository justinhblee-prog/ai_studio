export interface ApiRequestOptions {
  token?: string;
  method?: string;
  body?: unknown;
  signal?: AbortSignal;
}
export interface WorkspaceRecord {
  workspace_id: string;
  role?: string;
  owner_id?: string;
  created_at?: string;
}
export function apiRequest<T = any>(baseUrl: string, path: string, options?: ApiRequestOptions): Promise<T>;
export function createWorkspaceId(randomUUID?: () => string): string;
export function loadOrCreateWorkspace(baseUrl: string, token: string): Promise<{ workspace: WorkspaceRecord; workspaces: WorkspaceRecord[] }>;
