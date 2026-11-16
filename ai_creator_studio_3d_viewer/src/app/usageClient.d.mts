export type MemberUsage = { user_id: string; jobs: number; failed: number; services: Record<string, number> };
export type Usage = { workspace_id: string; month: string; scope: 'workspace' | 'self'; jobs: number; failed: number; services: Record<string, number>; limit: { monthly_jobs: number | null; counted_against_limit: number | null } | null; members: MemberUsage[] };
export function monthLabel(date: Date): string;
export function monthOptions(now?: Date): { value: string; label: string }[];
export function fetchUsage(api: string, token: string, workspaceId: string, month: string): Promise<Usage>;
export function limitBanner(counted: number | null | undefined, limit: number | null | undefined): { level: 80 | 100; text: string } | null;
export function usageCsv(usage: Partial<Usage> | null | undefined): string;
