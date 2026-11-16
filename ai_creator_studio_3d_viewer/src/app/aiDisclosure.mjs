// L-07: the label shown next to a generated output. An output is only called "AI-free" when the server says so;
// a missing value (older server) is shown as unknown rather than guessed.
// inputSource (reply 11 A): "uploaded" = made from the customer's own photos -> the result is an AI EDITED image; "platform_library_ai" = a library
// AI model/garment was used -> AI GENERATED; anything else keeps the careful wording "AI 생성물" (when in doubt, disclose generously).
export function aiDisclosureLabel(isAiGenerated, provider, model, inputSource) {
  if (isAiGenerated === true) {
    const by = [provider, model].filter(Boolean).join(' / ');
    const word = inputSource === 'uploaded' ? 'AI 편집 이미지' : inputSource === 'platform_library_ai' ? 'AI 생성 이미지' : 'AI 생성물';
    return { kind: 'ai', text: by ? `${word} · ${by}` : word };
  }
  if (isAiGenerated === false) return { kind: 'non-ai', text: 'AI 미사용 출력' };
  return { kind: 'unknown', text: 'AI 생성 여부 미확인' };
}
