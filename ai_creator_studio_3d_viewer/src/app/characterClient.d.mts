export const MIN_REFS: number;
export const MAX_REFS: number;
export function identityFromLibraryModel(item: { name_ko?: string; attributes?: Record<string, string> } | null | undefined, name?: string): Record<string, unknown>;
export function profileCard(character: { identity?: Record<string, any>; asset_ids?: string[] } | null | undefined): { name: string; summary: string; references: number };
export function validateProfile(input: { name?: string; assetIds?: string[] }): string;
export function listProfiles(api: string, token: string, workspaceId: string): Promise<{ items: any[] }>;
export function createProfile(api: string, token: string, workspaceId: string, input: { identity: Record<string, unknown>; assetIds: string[] }): Promise<any>;
export function deleteProfile(api: string, token: string, workspaceId: string, characterId: string): Promise<null>;
export function loadFeatures(api: string, token: string): Promise<{ features: Record<string, { enabled: boolean; status: string }> }>;
