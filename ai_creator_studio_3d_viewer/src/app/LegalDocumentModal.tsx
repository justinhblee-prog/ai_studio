import { Fragment, useEffect, useMemo, useRef } from 'react';
import type { KeyboardEvent } from 'react';
import { DOCUMENT_LABELS } from './legalApi.mjs';
import { LEGAL_DRAFT_BANNER, legalDocumentBlocks } from './legalMarkdown.mjs';
import type { InlinePart, LegalBlock } from './legalMarkdown.mjs';
import { LEGAL_SOURCES } from './legalDocs';

const Inline = ({ parts }: { parts: InlinePart[] }) => <>{parts.map((p, i) =>
  p.t === 'bold' ? <strong key={i}>{p.v}</strong> : p.t === 'code' ? <code key={i}>{p.v}</code> : <Fragment key={i}>{p.v}</Fragment>)}</>;

function Block({ block }: { block: LegalBlock }) {
  switch (block.type) {
    case 'heading': { const H = `h${Math.min(6, block.level + 1)}` as 'h2'; return <H><Inline parts={block.inline}/></H>; }
    case 'paragraph': return <p><Inline parts={block.inline}/></p>;
    case 'quote': return <blockquote><Inline parts={block.inline}/></blockquote>;
    case 'list': { const L = block.ordered ? 'ol' : 'ul'; return <L>{block.items.map((it, i) => <li key={i}><Inline parts={it}/></li>)}</L>; }
    case 'table': return <div className="legal-table-wrap"><table><thead><tr>{block.header.map((c, i) => <th key={i}><Inline parts={c}/></th>)}</tr></thead>
      <tbody>{block.rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j}><Inline parts={c}/></td>)}</tr>)}</tbody></table></div>;
  }
}

// Modal: Esc closes, focus moves into the dialog on open and returns to the opener on close, Tab stays inside.
export default function LegalDocumentModal({ document: doc, onClose }: { document: string; onClose: () => void }) {
  const title = DOCUMENT_LABELS[doc] || doc;
  const blocks = useMemo(() => legalDocumentBlocks(LEGAL_SOURCES[doc] || ''), [doc]);
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const opener = globalThis.document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    return () => opener?.focus?.();
  }, []);

  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Escape') { event.stopPropagation(); onClose(); return; }
    if (event.key !== 'Tab') return;
    const focusable = dialogRef.current?.querySelectorAll<HTMLElement>('button, [href], [tabindex]:not([tabindex="-1"])');
    if (!focusable?.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && globalThis.document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && globalThis.document.activeElement === last) { event.preventDefault(); first.focus(); }
  };

  return <div className="legal-modal-backdrop" onKeyDown={onKeyDown}>
    <div className="legal-modal" role="dialog" aria-modal="true" aria-labelledby="legal-doc-title" ref={dialogRef}>
      <div className="legal-modal-head"><h2 id="legal-doc-title">{title}</h2>
        <button className="text-button" ref={closeRef} onClick={onClose} aria-label={`${title} 닫기`}>닫기</button></div>
      <div className="auth-notice" role="note">{LEGAL_DRAFT_BANNER}</div>
      <div className="legal-modal-body">{blocks.map((b, i) => <Block key={i} block={b}/>)}</div>
    </div>
  </div>;
}
