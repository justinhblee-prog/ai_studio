import { useState } from 'react';
import LibraryBrowser from './LibraryBrowser';
import { GROUPS, groupOf, importLibraryItem } from './app/libraryClient.mjs';
import type { LibraryItem } from './app/libraryClient.mjs';
import './LibraryBrowser.css';
import { errorText } from './app/errorMessages.mjs';

type Props = { apiBaseUrl: string; accessToken: string; workspaceId: string };

// R-033: the "라이브러리" screen. Using an item copies it into this workspace's own assets (the original stays untouched).
export default function LibraryWorkspace({ apiBaseUrl, accessToken, workspaceId }: Props) {
  const [groupKey, setGroupKey] = useState(GROUPS[0].key);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const group = groupOf(groupKey);

  const doImport = async (item: LibraryItem) => {
    setError(''); setMessage('');
    try {
      await importLibraryItem(apiBaseUrl, accessToken, item.item_id, workspaceId);
      setMessage(`"${item.name_ko}"을(를) 내 자산에 가져왔습니다. 포토 스튜디오나 가상 착장 시험 생성의 "내 자산"에서 고를 수 있습니다.`);
    } catch (reason) {
      setError(errorText(reason, '가져오지 못했습니다.'));
    }
  };

  return <section className="module" aria-label="라이브러리">
    <div className="module-head"><div><small>LIBRARY</small><h1>기본 자산 라이브러리</h1>
      <p>서비스가 준비한 모델·의류·액세서리·배경입니다. "내 작업에 가져오기"를 누르면 내 작업공간 자산으로 복사되며, 원본은 바뀌지 않습니다.</p></div></div>
    <div className="lib-tabs" role="tablist" aria-label="라이브러리 종류">
      {GROUPS.map(g => <button key={g.key} type="button" role="tab" aria-selected={g.key === groupKey} onClick={() => { setGroupKey(g.key); setMessage(''); setError(''); }}>{g.label}</button>)}
    </div>
    {message && <div className="auth-notice" role="status">{message}</div>}
    {error && <div className="auth-error" role="alert">{error}</div>}
    <div role="tabpanel" aria-label={`${group.label} 항목`}>
      <LibraryBrowser apiBaseUrl={apiBaseUrl} accessToken={accessToken} categories={group.categories} actionLabel="내 작업에 가져오기" onAction={doImport}/>
    </div>
  </section>;
}
