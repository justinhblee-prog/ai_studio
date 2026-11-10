export const GENERATION_LIMIT_MESSAGES: Readonly<Record<string, string>>;
export function generationLimitMessage(code: unknown, detail?: { limit?: unknown; used?: unknown } | null): string | null;
