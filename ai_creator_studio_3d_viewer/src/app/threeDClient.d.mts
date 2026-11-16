export const BACKGROUNDS: readonly { value: string; label: string }[];
export const MAX_MODEL_BYTES: number;
export function validateModelFile(file: { name?: string; size: number } | null | undefined): string;
export function currentVersionId(versions: { items?: { version_id: string; is_current?: boolean }[] } | null | undefined): string | null;
export function modelContentUrl(api: string, assetId: string, versionId: string): string;
export function listModels(api: string, token: string, workspaceId: string): Promise<{ items: { asset_id: string; original_filename: string }[] }>;
export function listVersions(api: string, token: string, assetId: string): Promise<{ items: { version_id: string; is_current?: boolean }[] }>;
export function uploadModel(api: string, token: string, workspaceId: string, file: File): Promise<{ asset_id: string; original_filename: string }>;
