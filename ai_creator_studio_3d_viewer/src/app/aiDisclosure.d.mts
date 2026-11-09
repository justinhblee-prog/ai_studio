export function aiDisclosureLabel(isAiGenerated: boolean | null | undefined, provider?: string | null, model?: string | null): { kind: 'ai' | 'non-ai' | 'unknown'; text: string };
