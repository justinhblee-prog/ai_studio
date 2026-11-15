import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import {
  CATEGORY_LABELS, EMPTY_MESSAGE, LOAD_FAILED_MESSAGE, MODEL_FILTERS, labelsFor, libraryPreviewSrc, listLibraryItems,
} from './app/libraryClient.mjs';
import type { LibraryItem } from './app/libraryClient.mjs';
import './LibraryBrowser.css';

type Props = {
  apiBaseUrl: string; accessToken: string;
  categories: string[];              // the server categories this view may show (first one is selected first)
  actionLabel: string;               // button on each card
  onAction: (item: LibraryItem) => Promise<void>;
  busyExternal?: boolean;
};

function Thumb({ item, apiBaseUrl, accessToken }: { item: LibraryItem; apiBaseUrl: string; accessToken: string }) {
  const [src, setSrc] = useState('');
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true; setSrc(''); setFailed(false);
    libraryPreviewSrc(apiBaseUrl, accessToken, item.item_id).then(url => { if (live) setSrc(url); }).catch(() => { if (live) setFailed(true); });
    return () => { live = false; };
  }, [apiBaseUrl, accessToken, item.item_id, item.version]);
  if (failed) return <div className="lib-thumb-missing" role="img" aria-label={`${item.name_ko} 이미지를 불러오지 못했습니다`}>이미지를 불러오지 못했습니다</div>;
  return src ? <img src={src} alt={item.name_ko} loading="lazy" onError={() => setFailed(true)}/> : <div className="lib-thumb-missing">불러오는 중…</div>;
}

// R-033: category chips, search, model filters, card grid with "more", per-card action. Used by the Library screen and the asset pickers.
export default function LibraryBrowser({ apiBaseUrl, accessToken, categories, actionLabel, onAction, busyExternal }: Props) {
  const [category, setCategory] = useState(categories[0]);
  const [q, setQ] = useState('');
  const [submittedQ, setSubmittedQ] = useState('');
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [items, setItems] = useState<LibraryItem[] | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState('');
  const [large, setLarge] = useState('');
  const generation = useRef(0);

  useEffect(() => { setCategory(categories[0]); setFilters({}); setQ(''); setSubmittedQ(''); }, [categories.join(',')]); // eslint-disable-line react-hooks/exhaustive-deps

  const load = useCallback(async (append: boolean, from: string | null) => {
    const mine = ++generation.current;
    setError('');
    try {
      const result = await listLibraryItems(apiBaseUrl, accessToken, { category, q: submittedQ, attributes: category === 'model' ? filters : {}, cursor: append ? from : null });
      if (mine !== generation.current) return;
      setItems(current => (append ? [...(current ?? []), ...result.items] : result.items));
      setCursor(result.next_cursor);
    } catch {
      if (mine === generation.current) { setError(LOAD_FAILED_MESSAGE); if (!append) setItems([]); }
    }
  }, [apiBaseUrl, accessToken, category, submittedQ, filters]);

  useEffect(() => { setItems(null); load(false, null); }, [load]);

  const act = async (item: LibraryItem) => {
    setBusyId(item.item_id);
    try { await onAction(item); } finally { setBusyId(''); }
  };

  return <div className="lib-browser">
    {categories.length > 1 && <div className="lib-tabs" role="group" aria-label="종류">
      {categories.map(c => <button key={c} type="button" aria-pressed={c === category} onClick={() => setCategory(c)}>{CATEGORY_LABELS[c] ?? c}</button>)}
    </div>}
    <form className="lib-bar" onSubmit={(event: FormEvent) => { event.preventDefault(); setSubmittedQ(q); }}>
      <label>검색<input value={q} onChange={event => setQ(event.currentTarget.value)} maxLength={80} placeholder="이름·태그"/></label>
      {category === 'model' && Object.entries(MODEL_FILTERS).map(([key, def]) => <label key={key}>{def.label}
        <select value={filters[key] ?? ''} onChange={event => setFilters(current => ({ ...current, [key]: event.currentTarget.value }))}>
          <option value="">전체</option>
          {def.options.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select></label>)}
      <button type="submit" className="outline">검색</button>
    </form>
    {error && <div className="auth-error" role="alert">{error} <button type="button" className="outline" onClick={() => load(false, null)}>다시 시도</button></div>}
    {items === null && !error && <p role="status">불러오는 중…</p>}
    {items && items.length === 0 && !error && <p role="status">{EMPTY_MESSAGE}</p>}
    {items && items.length > 0 && <ul className="lib-grid" aria-label="라이브러리 항목">
      {items.map(item => <li key={item.item_id} className={`lib-card${large === item.item_id ? ' is-large' : ''}`} data-category={item.category}>
        <Thumb item={item} apiBaseUrl={apiBaseUrl} accessToken={accessToken}/>
        <b>{item.name_ko}</b>
        <div>{labelsFor(item).map(label => <span key={label} className={`lib-badge${label === 'AI 생성 이미지' ? ' ai' : ''}`}>{label}</span>)}</div>
        {item.category === 'model' && <small>{['age_range', 'body_type', 'hair', 'region_style'].map(key => MODEL_FILTERS[key].options.find(([v]) => v === item.attributes[key])?.[1]).filter(Boolean).join(' · ')}</small>}
        <div className="lib-actions">
          <button type="button" onClick={() => setLarge(current => (current === item.item_id ? '' : item.item_id))}>{large === item.item_id ? '작게' : '크게 보기'}</button>
          <button type="button" className="primary" disabled={!!busyId || busyExternal} onClick={() => act(item)}>{busyId === item.item_id ? '처리 중…' : actionLabel}</button>
        </div>
      </li>)}
    </ul>}
    {cursor && <p><button type="button" className="outline" onClick={() => load(true, cursor)}>더 보기</button></p>}
  </div>;
}
