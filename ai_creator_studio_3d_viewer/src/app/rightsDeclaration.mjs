// L-04: pure helpers for the rights / likeness declaration sent with an image upload.
export const RIGHTS_ERROR_CODES = ['RIGHTS_CONFIRMATION_REQUIRED', 'LIKENESS_CONSENT_REQUIRED'];

export function appendRightsDeclaration(form, { rightsConfirmed, depictsPerson, likenessConsent }) {
  form.set('rights_confirmed', String(Boolean(rightsConfirmed)));
  form.set('depicts_person', String(Boolean(depictsPerson)));
  // consent is only meaningful when a person is shown; never send a stale "true" after unchecking
  form.set('likeness_consent', String(Boolean(depictsPerson) && Boolean(likenessConsent)));
  return form;
}

// Returns the server's rights error code, or null for any other response.
export async function rightsErrorCode(response) {
  try {
    const code = (await response.clone().json())?.detail?.code;
    return RIGHTS_ERROR_CODES.includes(code) ? code : null;
  } catch {
    return null;
  }
}
