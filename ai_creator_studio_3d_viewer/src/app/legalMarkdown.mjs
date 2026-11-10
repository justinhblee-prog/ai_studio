// Tiny renderer for the legal drafts: headings, tables, bullet/numbered lists, blockquotes, **bold**, `code`.
// Output is plain data (no HTML strings), so the React view never needs dangerouslySetInnerHTML.
// Bracketed blanks such as [결정 필요] are ordinary text and are passed through unchanged.

const unescapeMd = (text) => text.replace(/\\([\\`*_{}\[\]()#+\-.!|>])/g, '$1');

export function parseInline(text) {
  const parts = [];
  const re = /\*\*(.+?)\*\*|`([^`]+)`/g;
  let last = 0;
  let m;
  const plain = (s) => { if (s) parts.push({ t: 'text', v: unescapeMd(s) }); };
  while ((m = re.exec(text))) {
    plain(text.slice(last, m.index));
    if (m[1] !== undefined) parts.push({ t: 'bold', v: unescapeMd(m[1]) });
    else parts.push({ t: 'code', v: m[2] });
    last = m.index + m[0].length;
  }
  plain(text.slice(last));
  return parts;
}

const splitRow = (line) => line.trim().replace(/^\|/, '').replace(/\|$/, '').split(/(?<!\\)\|/).map((c) => c.trim());
const isSeparator = (line) => /^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$/.test(line.trim());
const BULLET = /^\s*[-*]\s+(.*)$/;
const ORDERED = /^\s*\d+[.)]\s+(.*)$/;

export function parseLegalMarkdown(source) {
  const lines = String(source).replace(/\r\n?/g, '\n').split('\n');
  const blocks = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i += 1; continue; }
    const heading = /^(#{1,6})\s+(.*)$/.exec(line);
    if (heading) { blocks.push({ type: 'heading', level: heading[1].length, inline: parseInline(heading[2]) }); i += 1; continue; }
    if (line.startsWith('>')) {
      const quoted = [];
      while (i < lines.length && lines[i].startsWith('>')) { quoted.push(lines[i].replace(/^>\s?/, '')); i += 1; }
      blocks.push({ type: 'quote', inline: parseInline(quoted.join(' ').trim()) });
      continue;
    }
    if (line.trim().startsWith('|')) {
      const rows = [];
      while (i < lines.length && lines[i].trim().startsWith('|')) {
        if (!isSeparator(lines[i])) rows.push(splitRow(lines[i]).map(parseInline));
        i += 1;
      }
      blocks.push({ type: 'table', header: rows[0] || [], rows: rows.slice(1) });
      continue;
    }
    if (BULLET.test(line) || ORDERED.test(line)) {
      const ordered = ORDERED.test(line);
      const re = ordered ? ORDERED : BULLET;
      const items = [];
      while (i < lines.length && re.test(lines[i])) { items.push(parseInline(re.exec(lines[i])[1])); i += 1; }
      blocks.push({ type: 'list', ordered, items });
      continue;
    }
    const para = [];
    while (i < lines.length && lines[i].trim() && !/^(#{1,6}\s|>|\||\s*[-*]\s|\s*\d+[.)]\s)/.test(lines[i])) { para.push(lines[i].trim()); i += 1; }
    blocks.push({ type: 'paragraph', inline: parseInline(para.join(' ')) });
  }
  return blocks;
}

export const inlineText = (inline) => inline.map((p) => p.v).join('');

// What the screen shows: the developer-only note at the top and the author byline ("Nov 9, 2026 · @name") are dropped.
export function legalDocumentBlocks(source) {
  const blocks = parseLegalMarkdown(source);
  if (blocks[0]?.type === 'quote') blocks.shift();
  return blocks.filter((b) => !(b.type === 'paragraph' && /^[A-Z][a-z]{2} \d{1,2}, \d{4} · @/.test(inlineText(b.inline))));
}

export function blockText(block) {
  if (block.inline) return inlineText(block.inline);
  if (block.type === 'list') return block.items.map(inlineText).join('\n');
  if (block.type === 'table') return [block.header, ...block.rows].map((r) => r.map(inlineText).join(' | ')).join('\n');
  return '';
}

export const legalDocumentText = (source) => legalDocumentBlocks(source).map(blockText).join('\n');

export const LEGAL_DRAFT_BANNER = '초안 · 법률 검토 전입니다. 대괄호([ ])로 표시된 부분은 아직 확정되지 않은 빈칸이며 채우지 않았습니다. 확정되면 다시 동의를 요청합니다.';
