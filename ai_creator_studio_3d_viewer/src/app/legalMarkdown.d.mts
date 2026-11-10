export type InlinePart = { t: 'text' | 'bold' | 'code'; v: string };
export type LegalBlock =
  | { type: 'heading'; level: number; inline: InlinePart[] }
  | { type: 'paragraph' | 'quote'; inline: InlinePart[] }
  | { type: 'list'; ordered: boolean; items: InlinePart[][] }
  | { type: 'table'; header: InlinePart[][]; rows: InlinePart[][][] };
export function parseInline(text: string): InlinePart[];
export function parseLegalMarkdown(source: string): LegalBlock[];
export function legalDocumentBlocks(source: string): LegalBlock[];
export function blockText(block: LegalBlock): string;
export function legalDocumentText(source: string): string;
export const inlineText: (inline: InlinePart[]) => string;
export const LEGAL_DRAFT_BANNER: string;
