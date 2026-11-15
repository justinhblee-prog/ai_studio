export function isProtectedTarget(target: unknown): boolean;
export function blockIfProtected(event: { target?: unknown; preventDefault(): void }): boolean;
export function installImageGuard(doc?: Document): () => void;
export function watermarkText(name: string | null | undefined, when?: Date): string;
export function watermarkStyle(text: string): { backgroundImage: string; backgroundRepeat: string };
