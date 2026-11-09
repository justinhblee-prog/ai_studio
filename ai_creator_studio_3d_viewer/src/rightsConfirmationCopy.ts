// L-04: labels for the rights / likeness declaration shown before an image is added.
// PLACEHOLDER COPY: this is neutral UI wording, not approved legal text. The final wording must come from
// the legal documents and replace these strings before launch (tracked as a blocked item in docs/LAUNCH_STATUS.md).
export const RIGHTS_CONFIRMATION_COPY = {
  heading: '이미지 사용 확인',
  rightsConfirmed: '이 이미지를 사용할 권리가 있음을 확인합니다',
  depictsPerson: '이미지에 사람이 나옵니다',
  likenessConsent: '나오는 사람의 동의를 받았음을 확인합니다',
  rightsRequiredError: '이미지 사용 권리 확인에 체크한 뒤 이미지를 다시 추가해 주세요.',
  likenessRequiredError: '사람이 나오는 이미지는 해당 인물의 동의 확인에 체크한 뒤 다시 추가해 주세요.',
} as const;

// Server error codes that map to the messages above.
export const RIGHTS_ERROR_MESSAGES: Record<string, string> = {
  RIGHTS_CONFIRMATION_REQUIRED: RIGHTS_CONFIRMATION_COPY.rightsRequiredError,
  LIKENESS_CONSENT_REQUIRED: RIGHTS_CONFIRMATION_COPY.likenessRequiredError,
};
