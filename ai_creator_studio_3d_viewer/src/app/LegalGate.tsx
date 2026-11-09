import { useState } from 'react';
import { DOCUMENT_LABELS, acceptRequired, setConsent } from './legalApi.mjs';
import type { LegalStatus } from './legalApi.mjs';

// The document texts are not part of the app yet and the drafts are not final; this screen says so instead of implying otherwise.
export default function LegalGate({ api, token, status, onAccepted, onLogout }: {
  api: string; token: string; status: LegalStatus;
  onAccepted: (next: LegalStatus) => void; onLogout: () => void;
}) {
  const pending = status.missing.length ? status.missing : status.required;
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const [aiTraining, setAiTraining] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const allChecked = pending.every(d => checked[d.document]);

  const submit = async () => {
    setBusy(true); setError('');
    try {
      const next = await acceptRequired(api, token, status);
      // The optional consent is recorded only after the required acceptance succeeded, and only when the box was ticked.
      if (aiTraining) await setConsent(api, token, 'ai_training', true);
      onAccepted(next);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '동의 기록에 실패했습니다.');
    } finally { setBusy(false); }
  };

  return <div className="connect-page"><div className="connect-card legal-gate" role="dialog" aria-labelledby="legal-title">
    <small>SERVICE TERMS</small><h1 id="legal-title">서비스 이용 동의</h1>
    <div className="auth-notice" role="note">아래 문서는 <b>초안(draft)</b>이며 최종 법률 문서가 아닙니다. 파일럿 기간에만 사용되며, 문서가 확정되면 다시 동의를 요청합니다.</div>
    <ul className="legal-list">{pending.map(d => <li key={d.document}>
      <label><input type="checkbox" checked={Boolean(checked[d.document])} disabled={busy}
        onChange={e => setChecked({ ...checked, [d.document]: e.target.checked })}/>
        {' '}{DOCUMENT_LABELS[d.document] || d.document} <small>(버전 {d.version})</small>에 동의합니다 <b>(필수)</b></label></li>)}</ul>
    <div className="legal-optional"><label><input type="checkbox" checked={aiTraining} disabled={busy} onChange={e => setAiTraining(e.target.checked)}/>
      {' '}내 콘텐츠를 AI 모델 개선에 사용하는 것에 동의합니다 <b>(선택)</b></label>
      <small>선택 항목입니다. 동의하지 않아도 서비스를 사용할 수 있고, 설정에서 언제든 철회할 수 있습니다.</small></div>
    {error && <div className="auth-error" role="alert">{error}</div>}
    <button className="auth-submit" onClick={submit} disabled={busy || !allChecked}>{busy ? '기록 중…' : '동의하고 계속'}</button>
    <button className="text-button" onClick={onLogout} disabled={busy}>동의하지 않고 로그아웃</button>
  </div></div>;
}
