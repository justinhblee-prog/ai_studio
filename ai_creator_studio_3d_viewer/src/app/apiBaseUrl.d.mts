export const API_BASE_STORAGE_KEY: string;
export function isApiBaseEditable(options: { production: boolean }): boolean;
export function resolveApiBase(options: {
  production: boolean; configured?: string; readSaved?: () => string; hostname?: string;
}): string;
export function apiBaseConfigError(options: { production: boolean; base: string }): string;
