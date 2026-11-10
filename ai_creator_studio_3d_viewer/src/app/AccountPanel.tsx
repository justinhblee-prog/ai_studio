import { useCallback, useEffect, useState } from 'react';
import { cancelDeletionRequest, loadConsents, loadDeletionRequests, requestAccountDeletion, setConsent } from './legalApi.mjs';
import type { ConsentItem, DeletionRequest } from './legalApi.mjs';
import { DOCUMENT_LABELS } from './legalApi.mjs';
import LegalDocumentModal from './LegalDocumentModal';

// Shown inside the settings panel: the optional AI-training consent (withdrawable) and account deletion requests.
export default function AccountPanel({ api, token }: { api: string; token: string }) {
  const [consents, setConsents] = useState<ConsentItem[]>([]);
  const [requests, setRequests] = useState<DeletionRequest[]>([]);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [viewing, setViewing] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const [c, r] = await Promise.all([loadConsents(api, token), loadDeletionRequests(api, token)]);
      setConsents(c); setRequests(r); setError('');
    } catch (reason) { setError(reason instanceof Error ? reason.message : '계정 정보를 불러오지 못했습니다.'); }
  }, [api, token]);
  useEffect(() => { void reload(); }, [reload]);

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError('');
    try { await fn(); await reload(); } catch (reason) { setError(reason instanceof Error ? reason.message : '요청에 실패했습니다.'); }
    finally { setBusy(false); }
  };
  const ai = consents.find(c => c.purpose === 'ai_training');
  const open = requests.find(r => r.status === 'pending');

  return <div className="account-panel">
    <div className="settings-title"><b>개인정보와 데이터</b><span>동의 철회와 삭제 요청은 여기서 할 수 있습니다.</span></div>
    {error && <div className="auth-error" role="alert">{error}</div>}
    <div className="account-legal"><b>약관·방침 본문</b>
      {['terms', 'privacy', 'content_policy'].map(d => <button key={d} type="button" className="outline" onClick={() => setViewing(d)}
        aria-label={`${DOCUMENT_LABELS[d]} 본문 보기`}>{DOCUMENT_LABELS[d]} 보기</button>)}
      <small>법률 검토 전 초안입니다.</small></div>
    {viewing && <LegalDocumentModal document={viewing} onClose={() => setViewing(null)}/>}
    <label className="account-consent"><input type="checkbox" checked={Boolean(ai?.granted)} disabled={busy || !ai}
      onChange={e => act(() => setConsent(api, token, 'ai_training', e.target.checked))}/>
      {' '}내 콘텐츠를 AI 모델 개선에 사용하는 것에 동의 <small>(선택, 철회는 즉시 반영)</small></label>
    <div className="account-delete">
      <b>계정 데이터 삭제 요청</b>
      <p>요청은 <b>기록만</b> 되며 즉시 삭제되지 않습니다. 운영자가 유예기간(7일)이 지난 뒤 처리하고, 유예기간 안에는 취소할 수 있습니다. 백업에 남은 사본은 보관 기간(30일) 뒤 폐기됩니다.</p>
      {open ? <div className="auth-notice" role="status">삭제 요청이 접수되어 있습니다 ({new Date(open.requested_at).toLocaleString()}).
        <button className="outline" disabled={busy} onClick={() => act(() => cancelDeletionRequest(api, token, open.request_id))}>요청 취소</button></div>
      : <><label>사유(선택)<input value={reason} maxLength={500} onChange={e => setReason(e.target.value)} disabled={busy}/></label>
        <button className="outline danger" disabled={busy} onClick={() => { if (window.confirm('계정 데이터 삭제를 요청할까요? 유예기간 안에는 취소할 수 있습니다.')) act(async () => { await requestAccountDeletion(api, token, reason); setReason(''); }); }}>계정 삭제 요청</button></>}
      {requests.some(r => r.status !== 'pending') && <small>지난 요청: {requests.filter(r => r.status !== 'pending').map(r => `${r.status === 'cancelled' ? '취소됨' : '처리됨'}`).join(', ')}</small>}
    </div>
  </div>;
}
