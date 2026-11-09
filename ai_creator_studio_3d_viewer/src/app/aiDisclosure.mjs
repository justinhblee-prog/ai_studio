// L-07: the label shown next to a generated output. An output is only called "AI-free" when the server says so;
// a missing value (older server) is shown as unknown rather than guessed.
export function aiDisclosureLabel(isAiGenerated, provider, model) {
  if (isAiGenerated === true) {
    const by = [provider, model].filter(Boolean).join(' / ');
    return { kind: 'ai', text: by ? `AI 생성물 · ${by}` : 'AI 생성물' };
  }
  if (isAiGenerated === false) return { kind: 'non-ai', text: 'AI 미사용 출력' };
  return { kind: 'unknown', text: 'AI 생성 여부 미확인' };
}
