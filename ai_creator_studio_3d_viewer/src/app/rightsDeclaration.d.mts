export const RIGHTS_ERROR_CODES: string[];
export function appendRightsDeclaration(form: FormData, declaration: { rightsConfirmed: boolean; depictsPerson: boolean; likenessConsent: boolean }): FormData;
export function rightsErrorCode(response: Response): Promise<string | null>;
