import { useCallback, useEffect, useRef, useState } from 'react';
import './OutputReviewWorkspace.css';
import { useRequestScope } from './useRequestScope';
import { KeyedRequestGate } from './keyedRequestGate.mjs';
import { AuthenticatedPreviewObjectUrls } from './authenticatedPreviewObjectUrls.mjs';
import { aiDisclosureLabel } from './app/aiDisclosure.mjs';

type GeneratedOutput = {
  id: string;
  job_id: string;
  mime_type: string;
  size_bytes: number;
  created_at: string;
  checksum_sha256?: string | null;
  asset_link_status: string;
  asset_id?: string | null;
  asset_version_id?: string | null;
  provenance_record_id?: string | null;
  is_ai_generated?: boolean | null;
  provider?: string | null;
  model?: string | null;
};

type ReviewEvent = {
  event_id: string;
  actor_id: string;
  decision: 'approved' | 'changes_requested' | 'rejected';
  comment: string;
  asset_id: string;
  asset_version_id: string;
  provenance_id: string;
  checksum_sha256: string;
  created_at: string;
};

type OutputReview = {
  output: {
    output_id: string;
    job_id: string;
    media_type: string;
    size_bytes: number;
    created_at: string;
    provider?: string | null;
    model?: string | null;
    asset_link_status: string;
    asset_id?: string | null;
    asset_version_id?: string | null;
    provenance_id?: string | null;
    checksum_sha256?: string | null;
    is_ai_generated?: boolean | null;
  };
  status: string;
  latest_decision?: ReviewEvent | null;
  events: ReviewEvent[];
  job_status: string;
};

export type OutputReviewWorkspaceProps = {
  apiBaseUrl: string;
  accessToken: string;
  jobId: string;
};

async function responseError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    const detail = body?.detail;
    return typeof detail === 'string' ? detail : detail?.message || `요청 실패 (${response.status})`;
  } catch {
    return `요청 실패 (${response.status})`;
  }
}

export default function OutputReviewWorkspace({ apiBaseUrl, accessToken, jobId }: OutputReviewWorkspaceProps) {
  const base = apiBaseUrl.replace(/\/$/, '');
  const headers = { Authorization: `Bearer ${accessToken}` };
  const { capture: captureScope, isCurrent: isScopeCurrent } = useRequestScope([base, accessToken, jobId]);
  const [outputs, setOutputs] = useState<GeneratedOutput[]>([]);
  const [reviews, setReviews] = useState<Record<string, OutputReview>>({});
  const [previewUrls, setPreviewUrls] = useState<Record<string, string>>({});
  const [previewErrors, setPreviewErrors] = useState<Record<string, string>>({});
  const [previewLoading, setPreviewLoading] = useState<Record<string, boolean>>({});
  const [previewExpiries, setPreviewExpiries] = useState<Record<string, number>>({});
  const [comment, setComment] = useState('');
  const [manifest, setManifest] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loadSequenceRef = useRef(0);
  const previewRequestGateRef = useRef(new KeyedRequestGate());
  const previewObjectUrlsRef = useRef(new AuthenticatedPreviewObjectUrls());
  const reviewMutationInFlightRef = useRef(false);

  useEffect(() => () => previewObjectUrlsRef.current.clear(), []);

  const load = useCallback(async (signal?: AbortSignal) => {
    const scope = captureScope();
    const requestId = ++loadSequenceRef.current;
    const response = await fetch(`${base}/v1/generation-jobs/${encodeURIComponent(jobId)}/outputs`, { headers, signal });
    if (signal?.aborted || !isScopeCurrent(scope) || requestId !== loadSequenceRef.current) return;
    if (!response.ok) throw new Error(await responseError(response));
    const result = await response.json() as { data: GeneratedOutput[] };
    if (signal?.aborted || !isScopeCurrent(scope) || requestId !== loadSequenceRef.current) return;
    setOutputs(result.data);
    setReviews({});
    previewRequestGateRef.current.invalidateAll();
    previewObjectUrlsRef.current.clear();
    setPreviewUrls({}); setPreviewErrors({}); setPreviewLoading({}); setPreviewExpiries({});
    const reviewEntries = await Promise.all(result.data.map(async (output) => {
      const reviewResponse = await fetch(`${base}/v1/generation-jobs/${encodeURIComponent(jobId)}/outputs/${encodeURIComponent(output.id)}/review`, { headers, signal });
      if (signal?.aborted || !isScopeCurrent(scope) || requestId !== loadSequenceRef.current) return [output.id, null] as const;
      if (!reviewResponse.ok) throw new Error(await responseError(reviewResponse));
      return [output.id, await reviewResponse.json() as OutputReview] as const;
    }));
    if (signal?.aborted || !isScopeCurrent(scope) || requestId !== loadSequenceRef.current) return;
    const reviewMap = Object.fromEntries(reviewEntries.filter((entry) => entry[1] !== null)) as Record<string, OutputReview>;
    setReviews(reviewMap);
    const previewEntries = await Promise.all(result.data.map(async (output) => {
      const review = reviewMap[output.id];
      const assetId = review?.output.asset_id;
      const versionId = review?.output.asset_version_id;
      const previewRequestId = previewRequestGateRef.current.next(output.id);
      if (!assetId || !versionId) return [output.id, '', '불변 AssetVersion 연결이 없어 미리보기를 사용할 수 없습니다.', 0, previewRequestId] as const;
      try {
        const previewResponse = await fetch(`${base}/v1/assets/${encodeURIComponent(assetId)}/versions/${encodeURIComponent(versionId)}/preview-content`, { headers, signal });
        if (signal?.aborted || !isScopeCurrent(scope) || requestId !== loadSequenceRef.current || !previewRequestGateRef.current.isCurrent(output.id, previewRequestId)) return [output.id, '', '', 0, previewRequestId] as const;
        if (!previewResponse.ok) throw new Error(await responseError(previewResponse));
        const previewBlob = await previewResponse.blob();
        if (!previewRequestGateRef.current.isCurrent(output.id, previewRequestId)) return [output.id, '', '', 0, previewRequestId] as const;
        return [output.id, previewObjectUrlsRef.current.replace(output.id, previewBlob), '', 0, previewRequestId] as const;
      } catch (reason) {
        if (!previewRequestGateRef.current.isCurrent(output.id, previewRequestId)) return [output.id, '', '', 0, previewRequestId] as const;
        return [output.id, '', reason instanceof Error ? reason.message : 'AssetVersion 미리보기를 발급하지 못했습니다.', 0, previewRequestId] as const;
      }
    }));
    if (!signal?.aborted && isScopeCurrent(scope) && requestId === loadSequenceRef.current) {
      setPreviewUrls((current) => {
        const next = { ...current };
        for (const [id, url, , , previewRequestId] of previewEntries) {
          if (!previewRequestGateRef.current.isCurrent(id, previewRequestId)) continue;
          if (url) next[id] = url; else delete next[id];
        }
        return next;
      });
      setPreviewErrors((current) => {
        const next = { ...current };
        for (const [id, , message, , previewRequestId] of previewEntries) {
          if (!previewRequestGateRef.current.isCurrent(id, previewRequestId)) continue;
          if (message) next[id] = message; else delete next[id];
        }
        return next;
      });
      setPreviewExpiries((current) => {
        const next = { ...current };
        for (const [id, , , expiry, previewRequestId] of previewEntries) {
          if (!previewRequestGateRef.current.isCurrent(id, previewRequestId)) continue;
          if (expiry) next[id] = expiry; else delete next[id];
        }
        return next;
      });
    }
  }, [base, accessToken, jobId, captureScope, isScopeCurrent]);

  useEffect(() => {
    loadSequenceRef.current += 1;
    previewRequestGateRef.current.invalidateAll();
    previewObjectUrlsRef.current.clear();
    setOutputs([]); setReviews({}); setPreviewUrls({}); setPreviewErrors({}); setPreviewLoading({}); setPreviewExpiries({}); setComment(''); setManifest(null); setError(null); setBusy(false);
    reviewMutationInFlightRef.current = false;
  }, [base, accessToken, jobId]);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : '생성 결과를 불러오지 못했습니다.');
    });
    return () => controller.abort();
  }, [load]);

  const loadOutputPreview = useCallback(async (outputId: string) => {
    const scope = captureScope();
    const review = reviews[outputId];
    const assetId = review?.output.asset_id;
    const versionId = review?.output.asset_version_id;
    if (!assetId || !versionId) {
      setPreviewErrors((current) => ({ ...current, [outputId]: '불변 AssetVersion 연결이 없어 미리보기를 사용할 수 없습니다.' }));
      return;
    }
    const requestId = previewRequestGateRef.current.next(outputId);
    setPreviewLoading((current) => ({ ...current, [outputId]: true }));
    setPreviewErrors((current) => { const next = { ...current }; delete next[outputId]; return next; });
    previewObjectUrlsRef.current.revoke(outputId);
    setPreviewUrls((current) => { const next = { ...current }; delete next[outputId]; return next; });
    setPreviewExpiries((current) => { const next = { ...current }; delete next[outputId]; return next; });
    try {
      const response = await fetch(`${base}/v1/assets/${encodeURIComponent(assetId)}/versions/${encodeURIComponent(versionId)}/preview-content`, { headers });
      if (!response.ok) throw new Error(await responseError(response));
      const blob = await response.blob();
      if (!isScopeCurrent(scope) || !previewRequestGateRef.current.isCurrent(outputId, requestId)) return;
      setPreviewUrls((current) => ({ ...current, [outputId]: previewObjectUrlsRef.current.replace(outputId, blob) }));
    } catch (reason) {
      if (isScopeCurrent(scope) && previewRequestGateRef.current.isCurrent(outputId, requestId)) setPreviewErrors((current) => ({ ...current, [outputId]: reason instanceof Error ? reason.message : 'AssetVersion 미리보기를 불러오지 못했습니다.' }));
    } finally {
      if (isScopeCurrent(scope) && previewRequestGateRef.current.isCurrent(outputId, requestId)) setPreviewLoading((current) => ({ ...current, [outputId]: false }));
    }
  }, [base, accessToken, reviews, captureScope, isScopeCurrent]);

  const handlePreviewImageError = useCallback((outputId: string, failedUrl: string) => {
    if (previewUrls[outputId] !== failedUrl) return;
    previewObjectUrlsRef.current.revoke(outputId);
    setPreviewUrls((current) => { const next = { ...current }; delete next[outputId]; return next; });
    previewRequestGateRef.current.invalidate(outputId);
    setPreviewExpiries((current) => { const next = { ...current }; delete next[outputId]; return next; });
    setPreviewLoading((current) => ({ ...current, [outputId]: false }));
    setPreviewErrors((current) => ({ ...current, [outputId]: '접근 권한이 없거나 이미지를 불러오지 못했습니다. 권한과 AssetVersion을 확인한 뒤 다시 시도해 주세요.' }));
  }, [previewUrls]);

  const decide = useCallback(async (outputId: string, action: 'approve' | 'request-changes' | 'reject') => {
    if (reviewMutationInFlightRef.current || (action !== 'approve' && !comment.trim())) return;
    const scope = captureScope();
    reviewMutationInFlightRef.current = true;
    setBusy(true); setError(null); setManifest(null);
    try {
      const response = await fetch(`${base}/v1/generation-jobs/${encodeURIComponent(jobId)}/outputs/${encodeURIComponent(outputId)}/review/${action}`, {
        method: 'POST', headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ comment: comment.trim() }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      if (!isScopeCurrent(scope)) return;
      setComment('');
      await load();
    } catch (reason) {
      if (isScopeCurrent(scope)) setError(reason instanceof Error ? reason.message : '검토 상태를 저장하지 못했습니다.');
    } finally {
      if (isScopeCurrent(scope)) { reviewMutationInFlightRef.current = false; setBusy(false); }
    }
  }, [base, accessToken, jobId, comment, load, captureScope, isScopeCurrent]);

  const exportManifest = useCallback(async () => {
    if (reviewMutationInFlightRef.current) return;
    const scope = captureScope();
    reviewMutationInFlightRef.current = true;
    setBusy(true); setError(null);
    try {
      const response = await fetch(`${base}/v1/generation-jobs/${encodeURIComponent(jobId)}/outputs/export-manifest`, { method: 'POST', headers });
      if (!response.ok) throw new Error(await responseError(response));
      const result = await response.json();
      if (!isScopeCurrent(scope)) return;
      setManifest(JSON.stringify(result, null, 2));
    } catch (reason) {
      if (isScopeCurrent(scope)) setError(reason instanceof Error ? reason.message : '내보내기 manifest를 만들지 못했습니다.');
    } finally {
      if (isScopeCurrent(scope)) { reviewMutationInFlightRef.current = false; setBusy(false); }
    }
  }, [base, accessToken, jobId, captureScope, isScopeCurrent]);

  return (
    <section className="acs-output-review" aria-label="생성 결과 검수 작업실">
      <header><div><strong>생성 결과 검수</strong><span>불변 AssetVersion · 생성 출처 · 승인 이력</span></div><button type="button" disabled={busy || outputs.length === 0} onClick={exportManifest}>승인 결과 manifest 내보내기</button></header>
      <p className="acs-output-review-notice">개별 결과의 검수 승인이 필요합니다. 내보내기는 내부 메타데이터 manifest만 생성하며, 공개 게시·상업적 이용 권리를 부여하지 않습니다.</p>
      {error && <p className="acs-output-review-error" role="alert">{error}</p>}
      {outputs.map((output) => {
        const review = reviews[output.id];
        const status = review?.status || 'loading';
        const terminal = status === 'approved' || status === 'rejected';
        const ready = status === 'pending_review' || status === 'changes_requested';
        const disclosure = aiDisclosureLabel(review?.output.is_ai_generated ?? output.is_ai_generated, output.provider ?? review?.output.provider, output.model ?? review?.output.model);
        return <article className="acs-output-review-item" key={output.id}>
          <div className="acs-output-review-heading"><strong>{output.id}</strong><span>{status}</span></div>
          <p className={`acs-ai-label acs-ai-label-${disclosure.kind}`} data-ai-disclosure={disclosure.kind}>{disclosure.text}</p>
          <p>{output.mime_type} · {output.size_bytes.toLocaleString()} bytes · Asset link: {output.asset_link_status}</p>
          {review?.output.asset_version_id && <><button type="button" disabled={!!previewLoading[output.id]} onClick={() => loadOutputPreview(output.id)}>{previewLoading[output.id] ? '미리보기 불러오는 중…' : previewUrls[output.id] ? '미리보기 새로고침' : '미리보기 불러오기 / 재시도'}</button>{previewErrors[output.id] && <small role="status">{previewErrors[output.id]}</small>}{previewExpiries[output.id] && <small>링크 만료 예정: {new Date(previewExpiries[output.id] * 1000).toLocaleTimeString()}</small>}</>}
          {previewUrls[output.id] && <img className="acs-output-review-preview" src={previewUrls[output.id]} alt="검수 대상 immutable AssetVersion 미리보기" loading="lazy" onError={(event) => handlePreviewImageError(output.id, event.currentTarget.src)} />}
          {review?.output.asset_version_id && <dl>
            <div><dt>Asset</dt><dd>{review.output.asset_id}</dd></div>
            <div><dt>Immutable Version</dt><dd>{review.output.asset_version_id}</dd></div>
            <div><dt>Provenance</dt><dd>{review.output.provenance_id}</dd></div>
            <div><dt>SHA-256</dt><dd>{review.output.checksum_sha256}</dd></div>
          </dl>}
          {review?.events?.length ? <ol className="acs-output-review-history">{review.events.map((event) => <li key={event.event_id}><strong>{event.decision}</strong> · {event.actor_id} · {new Date(event.created_at).toLocaleString()}{event.comment ? <p>{event.comment}</p> : null}</li>)}</ol> : null}
          {ready && <div className="acs-output-review-actions">
            <button type="button" disabled={busy} onClick={() => decide(output.id, 'approve')}>승인</button>
            <button type="button" disabled={busy || !comment.trim()} onClick={() => decide(output.id, 'request-changes')}>수정 요청</button>
            <button type="button" disabled={busy || !comment.trim()} onClick={() => decide(output.id, 'reject')}>반려</button>
          </div>}
          {terminal && <p className="acs-output-review-terminal">최종 상태입니다. 새 결과물을 생성해야 다시 검토할 수 있습니다.</p>}
        </article>;
      })}
      {outputs.length === 0 && <p>이 Job에 저장된 생성 결과가 없습니다.</p>}
      {outputs.some((output) => ['pending_review', 'changes_requested'].includes(reviews[output.id]?.status || '')) && <label className="acs-output-review-comment">검수 의견<input value={comment} maxLength={2000} onChange={(event) => setComment(event.currentTarget.value)} disabled={busy} placeholder="수정 요청 또는 반려 사유를 입력하세요" /></label>}
      {manifest && <pre className="acs-output-review-manifest">{manifest}</pre>}
    </section>
  );
}
