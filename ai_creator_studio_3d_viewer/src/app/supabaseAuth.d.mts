export interface SupabaseAuthConfig {
  url?: string;
  anonKey?: string;
  configured?: boolean;
}
export interface AuthSession {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_at: number;
  user?: { id?: string; email?: string } | null;
}
export interface AuthUser {
  id: string;
  email?: string;
  [key: string]: unknown;
}
export function normalizeSupabaseConfig(config?: SupabaseAuthConfig): SupabaseAuthConfig & { url: string; anonKey: string; configured: boolean };
export function signInWithPassword(config: SupabaseAuthConfig, email: string, password: string, fetchImpl?: typeof fetch): Promise<AuthSession>;
export function signUpWithPassword(config: SupabaseAuthConfig, email: string, password: string, fetchImpl?: typeof fetch): Promise<{ user: AuthUser | null; session: AuthSession | null }>;
export function getAuthenticatedUser(config: SupabaseAuthConfig, accessToken: string, fetchImpl?: typeof fetch): Promise<AuthUser>;
export function refreshSession(config: SupabaseAuthConfig, session: AuthSession, fetchImpl?: typeof fetch): Promise<AuthSession>;
export function signOut(config: SupabaseAuthConfig, session: AuthSession, fetchImpl?: typeof fetch): Promise<void>;
export function saveSession(session: AuthSession, storage?: Storage): void;
export function loadSession(storage?: Storage): AuthSession | null;
export function clearSession(storage?: Storage): void;
export function sessionFromLocationHash(hash?: string): AuthSession | null;
