import { useCallback, useEffect, useState } from 'react';
import type { GenerationJob } from './app/generationStart.mjs';
import {
  EMPTY_LIST_MESSAGE, NO_RESULT_MESSAGE, TEST_MARK, failureMessage, listGenerationJobs, loadJobResultBlob, statusGroup, statusLabel,
} from './app/jobResults.mjs';

type Props = { apiBaseUrl: string; accessToken: string; workspaceId: string };

// R-027: my workspace's generation jobs (newest first), one job's status, and its result image when the server has one.
export default function JobResultsWorkspace({ apiBaseUrl, accessToken, workspaceId }: Props) {
  const [jobs, setJobs] = useState<GenerationJob[] | null>(null);
  const [selected, setSelected] = useState<GenerationJob | null>(null);
  const [imageUrl, setImageUrl] = useState('');
  const [imageState, setImageState] = useState<'none' | 'loading' | 'ready' | 'missing'>('none');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setBusy(true); setError('');
    try {
      const items = await listGenerationJobs(apiBaseUrl, accessToken, workspaceId);
      setJobs(items);
      setSelected(current => (current ? items.find(item => item.job_id === current.job_id) ?? null : null));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '작업 목록을 불러오지 못했습니다.');
    } finally { setBusy(false); }
  }, [apiBaseUrl, accessToken, workspaceId]);

  useEffect(() => { setJobs(null); setSelected(null); refresh(); }, [refresh]);

  useEffect(() => {
    let revoked = false; let created = '';
    setImageUrl(''); setImageState('none');
    if (!selected || statusGroup(selected.status) !== 'done') return undefined;
    setImageState('loading');
    loadJobResultBlob(apiBaseUrl, accessToken, selected).then(blob => {
      if (revoked) return;
      if (!blob) { setImageState('missing'); return; }
      created = URL.createObjectURL(blob); setImageUrl(created); setImageState('ready');
    }).catch((reason: unknown) => { if (!revoked) { setImageState('missing'); setError(reason instanceof Error ? reason.message : '결과 이미지를 불러오지 못했습니다.'); } });
    return () => { revoked = true; if (created) URL.revokeObjectURL(created); };
  }, [apiBaseUrl, accessToken, selected]);

  const group = selected ? statusGroup(selected.status) : 'unknown';
  return <section className="module" aria-label="생성 작업 결과">
    <div className="module-head"><div><small>VIRTUAL TRY-ON</small><h1>생성 작업 <span className="tag">{TEST_MARK}</span></h1>
      <p>시작한 가상 착장 시험 생성 작업의 상태와 결과를 확인합니다. 지금은 시험(mock) 모드입니다.</p></div>
      <button type="button" className="outline" onClick={refresh} disabled={busy}>{busy ? '불러오는 중…' : '새로고침'}</button></div>
    {error && <div className="auth-error" role="alert">{error}</div>}
    {jobs && jobs.length === 0 && <div className="auth-notice" role="status">{EMPTY_LIST_MESSAGE}</div>}
    {jobs && jobs.length > 0 && <ul className="job-list" aria-label="작업 목록">
      {jobs.map(job => <li key={job.job_id}>
        <button type="button" className={selected?.job_id === job.job_id ? 'primary' : 'outline'} onClick={() => setSelected(job)} aria-pressed={selected?.job_id === job.job_id}>
          <code>{job.job_id}</code> · <b data-status={statusGroup(job.status)}>{statusLabel(job.status)}</b>{job.provider === 'mock' ? ` · ${TEST_MARK}` : ''}
        </button></li>)}
    </ul>}
    {selected && <div className="auth-notice" role="status" aria-label="작업 상세">
      <div>작업 ID: <code>{selected.job_id}</code></div>
      <div>상태: <b>{statusLabel(selected.status)}</b> · 엔진: {selected.provider}{selected.provider === 'mock' ? ` (${TEST_MARK})` : ''}</div>
      {group === 'failed' && <div role="alert">{failureMessage(selected.error_code)}{selected.error_code ? <small> (오류 코드: {selected.error_code})</small> : null}</div>}
      {(group === 'waiting' || group === 'running') && <div>작업이 처리되는 중입니다. 잠시 후 새로고침해 주세요.</div>}
      {group === 'done' && imageState === 'loading' && <div>결과 이미지를 불러오는 중…</div>}
      {group === 'done' && imageState === 'missing' && <div>{NO_RESULT_MESSAGE}</div>}
      {group === 'done' && imageState === 'ready' && <figure><img src={imageUrl} alt="생성 결과 이미지 (시험 생성)" style={{ maxWidth: '100%' }}/><figcaption>{TEST_MARK} · AI 생성 이미지 표시 대상</figcaption></figure>}
    </div>}
  </section>;
}
