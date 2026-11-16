import { FormEvent, useCallback, useEffect, useState } from 'react';
import LibraryBrowser from './LibraryBrowser';
import { apiRequest } from './app/apiClient.mjs';
import { createProfile, deleteProfile, identityFromLibraryModel, listProfiles, loadFeatures, MAX_REFS, profileCard, validateProfile } from './app/characterClient.mjs';
import { errorText } from './app/errorMessages.mjs';
import { importLibraryItem } from './app/libraryClient.mjs';
import type { LibraryItem } from './app/libraryClient.mjs';

type Props = { apiBaseUrl: string; accessToken: string; workspaceId: string };
type Profile = { character_id: string; identity: Record<string, any>; asset_ids: string[] };
type Image = { asset_id: string; original_filename: string };

// R-039: brand model profiles (Character Studio, profile part). Creating is off until the administrator switches FEATURE_CHARACTER on.
export default function CharacterWorkspace({ apiBaseUrl, accessToken, workspaceId }: Props) {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [profiles, setProfiles] = useState<Profile[] | null>(null);
  const [images, setImages] = useState<Image[]>([]);
  const [name, setName] = useState('');
  const [picked, setPicked] = useState<string[]>([]);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      const [features, list, assets] = await Promise.all([
        loadFeatures(apiBaseUrl, accessToken), listProfiles(apiBaseUrl, accessToken, workspaceId),
        apiRequest(apiBaseUrl, `/v1/assets?workspace_id=${encodeURIComponent(workspaceId)}&kind=image`, { token: accessToken }),
      ]);
      setEnabled(Boolean(features?.features?.character?.enabled));
      setProfiles(list?.items ?? []); setImages(assets?.items ?? []);
    } catch (reason) { setError(errorText(reason, '프로필을 불러오지 못했습니다.')); setProfiles([]); }
  }, [apiBaseUrl, accessToken, workspaceId]);
  useEffect(() => { setProfiles(null); load(); }, [load]);

  const toggle = (id: string) => setPicked(current => (current.includes(id) ? current.filter(x => x !== id) : [...current, id]));
  const problem = validateProfile({ name, assetIds: picked });

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!enabled || busy || problem) return;
    setBusy(true); setError(''); setMessage('');
    try {
      await createProfile(apiBaseUrl, accessToken, workspaceId, { identity: { name: name.trim() }, assetIds: picked });
      setName(''); setPicked([]); setMessage(`"${name.trim()}" 프로필을 만들었습니다.`); await load();
    } catch (reason) { setError(errorText(reason, '프로필을 만들지 못했습니다.')); } finally { setBusy(false); }
  };

  const fromLibrary = async (item: LibraryItem) => {
    if (!enabled) return;
    setError(''); setMessage('');
    try {
      const copy = await importLibraryItem(apiBaseUrl, accessToken, item.item_id, workspaceId);
      await createProfile(apiBaseUrl, accessToken, workspaceId, { identity: identityFromLibraryModel(item), assetIds: [copy.asset_id] });
      setMessage(`"${item.name_ko}" 모델로 프로필을 만들었습니다(내 자산으로 복사됨).`); await load();
    } catch (reason) { setError(errorText(reason, '프로필을 만들지 못했습니다.')); }
  };

  const remove = async (id: string) => {
    setError('');
    try { await deleteProfile(apiBaseUrl, accessToken, workspaceId, id); setConfirming(''); await load(); }
    catch (reason) { setError(errorText(reason, '프로필을 삭제하지 못했습니다.')); }
  };

  return <section className="module" aria-label="캐릭터 프로필">
    <div className="module-head"><div><small>CHARACTER</small><h1>브랜드 모델 프로필</h1>
      <p>기준 이미지 {1}~{MAX_REFS}장과 모델 속성을 묶어 브랜드 모델 프로필로 저장합니다. 속성은 고르기 쉽게 거르는 표시일 뿐 실제 인물에 대한 설명이 아닙니다.</p></div></div>
    {enabled === false && <div className="warning" role="status"><b>파일럿 시험판</b><span>캐릭터 스튜디오는 아직 시험판입니다. 관리자가 켜면 프로필을 만들 수 있습니다. 지금은 만든 프로필을 보기만 할 수 있습니다.</span></div>}
    {error && <div className="auth-error" role="alert">{error} <button type="button" className="outline" onClick={load}>다시 시도</button></div>}
    {message && <div className="auth-notice" role="status">{message}</div>}
    <form className="gen-form" onSubmit={submit} aria-label="내 사진으로 프로필 만들기">
      <h2>내 사진으로 만들기</h2>
      <label>프로필 이름<input value={name} maxLength={120} onChange={e => setName(e.currentTarget.value)} disabled={!enabled || busy}/></label>
      <fieldset disabled={!enabled || busy}><legend>기준 이미지 ({picked.length}/{MAX_REFS})</legend>
        {images.length === 0 ? <p>내 자산에 이미지가 없습니다. 포토 스튜디오나 라이브러리에서 먼저 추가해 주세요.</p>
          : images.map(img => <label key={img.asset_id}><input type="checkbox" checked={picked.includes(img.asset_id)} onChange={() => toggle(img.asset_id)}
              disabled={!picked.includes(img.asset_id) && picked.length >= MAX_REFS}/> {img.original_filename}</label>)}
      </fieldset>
      {problem && enabled && (name || picked.length) ? <small role="status">{problem}</small> : null}
      <button type="submit" className="primary" disabled={!enabled || busy || !!problem}>프로필 만들기</button>
    </form>
    <h2>라이브러리 모델에서 만들기</h2>
    <LibraryBrowser apiBaseUrl={apiBaseUrl} accessToken={accessToken} categories={['model']} actionLabel="프로필 만들기" busyExternal={!enabled} onAction={fromLibrary}/>
    <h2>내 프로필</h2>
    {profiles && profiles.length === 0 && <p role="status">아직 프로필이 없습니다.</p>}
    <ul className="lib-grid" aria-label="프로필 목록">
      {(profiles ?? []).map(p => { const card = profileCard(p); return <li key={p.character_id} className="lib-card">
        <b>{card.name}</b><small>{card.summary || '속성 없음'}</small><small>기준 이미지 {card.references}장</small>
        <div className="lib-actions">{confirming === p.character_id
          ? <><button type="button" className="outline" onClick={() => remove(p.character_id)}>정말 삭제</button><button type="button" className="outline" onClick={() => setConfirming('')}>취소</button></>
          : <button type="button" className="outline" onClick={() => setConfirming(p.character_id)}>삭제</button>}</div></li>; })}
    </ul>
  </section>;
}
