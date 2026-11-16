export const NOTICE_CODE: string;
export function noticeFromError(error: unknown): { provider: string; lines: string[] } | null;
export function acknowledgeNotice(api: string, token: string, workspaceId: string, provider: string): Promise<{ provider: string; acknowledged: boolean; acknowledged_at: string }>;
