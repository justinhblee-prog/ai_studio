export const MAX_STEPS: number;
export type StepParam = { key: string; label: string; type: 'int' | 'color'; min?: number; max?: number; value: number | string };
export const STEP_DEFS: Readonly<Record<string, { label: string; help: string; params: StepParam[] }>>;
export type Step = { op: string; [key: string]: any };
export function newStep(op: string): Step;
export function validateSteps(steps: Step[] | null | undefined): string;
export function moveStep(steps: Step[], index: number, delta: number): Step[];
export function summarizeRecords(records: { op: string; size_in: number[]; size_out: number[] }[] | null | undefined): string[];
export function runPhotoSteps(api: string, token: string, workspaceId: string, assetId: string, steps: Step[]): Promise<{ asset: { asset_id: string; original_filename: string }; steps: any[] }>;
