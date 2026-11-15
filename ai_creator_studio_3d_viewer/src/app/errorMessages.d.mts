export const MESSAGES: Readonly<Record<'network' | 'unauthorized' | 'forbidden' | 'notFound' | 'conflict' | 'tooLarge' | 'invalid' | 'tooMany' | 'server' | 'unknown', string>>;
export function messageForStatus(status: number | undefined, serverText?: string): string;
export function isNetworkError(reason: unknown): boolean;
export function errorText(reason: unknown, fallback?: string): string;
export function responseErrorText(response: Response): Promise<string>;
export const AUTH_FALLBACK: string;
export function authErrorText(reason: unknown): string;
