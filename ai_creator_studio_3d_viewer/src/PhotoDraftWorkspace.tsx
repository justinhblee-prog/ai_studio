import { RIGHTS_CONFIRMATION_COPY, RIGHTS_ERROR_MESSAGES } from './rightsConfirmationCopy';
import { appendRightsDeclaration, rightsErrorCode } from './app/rightsDeclaration.mjs';
import { ChangeEvent, FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import './PhotoDraftWorkspace.css';
import AssetSourceTabs from './AssetSourceTabs';
import LibraryBrowser from './LibraryBrowser';
import { importLibraryItem } from './app/libraryClient.mjs';
import { useRequestScope } from './useRequestScope';
import { KeyedRequestGate } from './keyedRequestGate.mjs';
import { AuthenticatedPreviewObjectUrls } from './authenticatedPreviewObjectUrls.mjs';

type ImageAsset = {
  asset_id: string;
  original_filename: string;
  media_type: string;
  size_bytes: number;
  checksum_sha256: string;
};

type PhotoOperation = 'ENHANCE' | 'BACKGROUND' | 'LIGHTING' | 'RETOUCH' | 'COMPOSE';
type OutputFormat = 'PNG' | 'JPEG' | 'WEBP';

type PhotoRun = {
  run_id: string;
  draft_id: string;
  workspace_id: string;
  created_by: string;
  processor_version: string;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  operation: PhotoOperation;
  status: 'processing' | 'succeeded' | 'failed';
  attempts: number;
  output_asset_id?: string | null;
  output_version_id?: string | null;
  output_checksum_sha256?: string | null;
  source_version_id?: string | null;
  source_checksum_sha256?: string | null;
  review_status?: string | null;
  quality: {
    is_ai_generated?: boolean;
    semantic_identity_preservation_verified?: boolean;
    text_and_logo_preservation_verified?: boolean;
    review_required?: boolean;
  };
};

type PhotoDraft = {
  draft_id: string;
  workspace_id: string;
  created_by: string;
  status: 'draft' | 'archived';
  created_at: string;
  updated_at: string;
  input: {
    source_asset_id: string;
    source_version_id?: string;
    source_checksum_sha256?: string;
    operation: PhotoOperation;
    preserve_identity: boolean;
    preserve_product_geometry: boolean;
    preserve_text_and_logo: boolean;
    target_style?: string | null;
    prompt?: string | null;
    output_format: OutputFormat;
    output_count: number;
  };
};

export type PhotoDraftWorkspaceProps = {
  apiBaseUrl: string;
  accessToken: string;
  workspaceId: string;
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

export function PhotoDraftWorkspace({ apiBaseUrl, accessToken, workspaceId }: PhotoDraftWorkspaceProps) {
  const [rightsConfirmed, setRightsConfirmed] = useState(false);
  const [depictsPerson, setDepictsPerson] = useState(false);
  const [likenessConsent, setLikenessConsent] = useState(false);
  const base = apiBaseUrl.replace(/\/$/, '');
  const headers = { Authorization: `Bearer ${accessToken}` };
  const { capture: captureScope, isCurrent: isScopeCurrent } = useRequestScope([base, accessToken, workspaceId]);
  const [images, setImages] = useState<ImageAsset[]>([]);
  const [drafts, setDrafts] = useState<PhotoDraft[]>([]);
  const [runsByDraft, setRunsByDraft] = useState<Record<string, PhotoRun[]>>({});
  const [reviewComment, setReviewComment] = useState('');
  const [manifestJson, setManifestJson] = useState<string | null>(null);
  const [previewUrls, setPreviewUrls] = useState<Record<string, string>>({});
  const [previewErrors, setPreviewErrors] = useState<Record<string, string>>({});
  const [previewLoading, setPreviewLoading] = useState<Record<string, boolean>>({});
  const [previewExpiries, setPreviewExpiries] = useState<Record<string, number>>({});
  const [sourceAssetId, setSourceAssetId] = useState('');
  const [operation, setOperation] = useState<PhotoOperation>('ENHANCE');
  const [outputFormat, setOutputFormat] = useState<OutputFormat>('PNG');
  const [outputCount, setOutputCount] = useState(1);
  const [targetStyle, setTargetStyle] = useState('');
  const [prompt, setPrompt] = useState('');
  const [preserveIdentity, setPreserveIdentity] = useState(true);
  const [preserveGeometry, setPreserveGeometry] = useState(true);
  const [preserveText, setPreserveText] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loadSequenceRef = useRef(0);
  const previewRequestGateRef = useRef(new KeyedRequestGate());
  const previewObjectUrlsRef = useRef(new AuthenticatedPreviewObjectUrls());
  const reviewMutationInFlightRef = useRef(false);

  const load = useCallback(async (signal?: AbortSignal) => {
    const scope = captureScope();
    const requestId = ++loadSequenceRef.current;
    const [imageResponse, draftResponse] = await Promise.all([
      fetch(`${base}/v1/assets?workspace_id=${encodeURIComponent(workspaceId)}&kind=image`, { headers, signal }),
      fetch(`${base}/v1/photo-drafts?workspace_id=${encodeURIComponent(workspaceId)}`, { headers, signal }),
    ]);
    if (!imageResponse.ok) throw new Error(await responseError(imageResponse));
    if (!draftResponse.ok) throw new Error(await responseError(draftResponse));
    const imageResult = await imageResponse.json() as { items: ImageAsset[] };
    const draftResult = await draftResponse.json() as { items: PhotoDraft[] };
    if (signal?.aborted || !isScopeCurrent(scope) || requestId !== loadSequenceRef.current) return;
    setImages(imageResult.items);
    setDrafts(draftResult.items);
    const runEntries = await Promise.all(draftResult.items.map(async (draft) => {
      const response = await fetch(`${base}/v1/photo-drafts/${encodeURIComponent(draft.draft_id)}/runs?workspace_id=${encodeURIComponent(workspaceId)}`, { headers, signal });
      if (!response.ok) throw new Error(await responseError(response));
      const result = await response.json() as { items: PhotoRun[] };
      return [draft.draft_id, result.items] as const;
    }));
    if (signal?.aborted || !isScopeCurrent(scope) || requestId !== loadSequenceRef.current) return;
    setRunsByDraft(Object.fromEntries(runEntries));
    setSourceAssetId((current) => current && imageResult.items.some((item) => item.asset_id === current) ? current : imageResult.items[0]?.asset_id || '');
  }, [base, accessToken, workspaceId, captureScope, isScopeCurrent]);

  useEffect(() => {
    previewObjectUrlsRef.current.clear();
    setImages([]); setDrafts([]); setRunsByDraft({}); setPreviewUrls({}); setPreviewErrors({}); setPreviewLoading({}); setPreviewExpiries({}); setSourceAssetId('');
    setReviewComment(''); setManifestJson(null); setError(null); setBusy(false);
    setTargetStyle(''); setPrompt(''); setOperation('ENHANCE'); setOutputFormat('PNG'); setOutputCount(1);
    setPreserveIdentity(true); setPreserveGeometry(true); setPreserveText(true);
    previewRequestGateRef.current.invalidateAll();
    reviewMutationInFlightRef.current = false;
  }, [base, accessToken, workspaceId]);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Photo Draft 정보를 불러오지 못했습니다.');
    });
    return () => controller.abort();
  }, [load]);

  const uploadImage = useCallback(async (event: ChangeEvent<HTMLInputElement>) => {
    const scope = captureScope();
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = '';
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.set('workspace_id', workspaceId);
      form.set('file', file);
      appendRightsDeclaration(form, { rightsConfirmed, depictsPerson, likenessConsent });
      const response = await fetch(`${base}/v1/assets/images`, { method: 'POST', headers, body: form });
      if (!response.ok) {
        const code = await rightsErrorCode(response);
        throw new Error(code ? RIGHTS_ERROR_MESSAGES[code] : await responseError(response));
      }
      const created = await response.json() as ImageAsset;
      if (!isScopeCurrent(scope)) return;
      await load();
      if (!isScopeCurrent(scope)) return;
      setSourceAssetId(created.asset_id);
    } catch (reason) {
      if (isScopeCurrent(scope)) setError(reason instanceof Error ? reason.message : '이미지를 업로드하지 못했습니다.');
    } finally {
      if (isScopeCurrent(scope)) { reviewMutationInFlightRef.current = false; setBusy(false); }
    }
  }, [base, accessToken, workspaceId, load, captureScope, isScopeCurrent, rightsConfirmed, depictsPerson, likenessConsent]);

  const createDraft = useCallback(async (event: FormEvent<HTMLFormElement>) => {
    const scope = captureScope();
    event.preventDefault();
    if (!sourceAssetId) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${base}/v1/photo-drafts`, {
        method: 'POST',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: workspaceId,
          source_asset_id: sourceAssetId,
          operation,
          preserve_identity: preserveIdentity,
          preserve_product_geometry: preserveGeometry,
          preserve_text_and_logo: preserveText,
          target_style: targetStyle.trim() || null,
          prompt: prompt.trim() || null,
          output_format: outputFormat,
          output_count: outputCount,
        }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      if (!isScopeCurrent(scope)) return;
      await load();
      if (!isScopeCurrent(scope)) return;
      setPrompt('');
    } catch (reason) {
      if (isScopeCurrent(scope)) setError(reason instanceof Error ? reason.message : 'Photo Draft를 저장하지 못했습니다.');
    } finally {
      if (isScopeCurrent(scope)) setBusy(false);
    }
  }, [base, accessToken, workspaceId, sourceAssetId, operation, preserveIdentity, preserveGeometry, preserveText, targetStyle, prompt, outputFormat, outputCount, load, captureScope, isScopeCurrent]);

  useEffect(() => () => previewObjectUrlsRef.current.clear(), []);

  const loadVersionPreview = useCallback(async (assetId: string, versionId: string) => {
    const scope = captureScope();
    const previewKey = `${assetId}:${versionId}`;
    const previewRequestId = previewRequestGateRef.current.next(previewKey);
    setPreviewLoading((current) => ({ ...current, [previewKey]: true }));
    setPreviewErrors((current) => { const next = { ...current }; delete next[previewKey]; return next; });
    previewObjectUrlsRef.current.revoke(previewKey);
    setPreviewUrls((current) => { const next = { ...current }; delete next[previewKey]; return next; });
    setPreviewExpiries((current) => { const next = { ...current }; delete next[previewKey]; return next; });
    try {
      const response = await fetch(`${base}/v1/assets/${encodeURIComponent(assetId)}/versions/${encodeURIComponent(versionId)}/preview-content`, { headers });
      if (!response.ok) throw new Error(await responseError(response));
      const blob = await response.blob();
      if (!isScopeCurrent(scope) || !previewRequestGateRef.current.isCurrent(previewKey, previewRequestId)) return;
      const objectUrl = previewObjectUrlsRef.current.replace(previewKey, blob);
      setPreviewUrls((current) => ({ ...current, [previewKey]: objectUrl }));
    } catch (reason) {
      if (isScopeCurrent(scope) && previewRequestGateRef.current.isCurrent(previewKey, previewRequestId)) {
        setPreviewErrors((current) => ({ ...current, [previewKey]: reason instanceof Error ? reason.message : 'AssetVersion 미리보기를 불러오지 못했습니다.' }));
      }
    } finally {
      if (isScopeCurrent(scope) && previewRequestGateRef.current.isCurrent(previewKey, previewRequestId)) setPreviewLoading((current) => ({ ...current, [previewKey]: false }));
    }
  }, [base, accessToken, captureScope, isScopeCurrent]);

  const handlePreviewImageError = useCallback((previewKey: string, failedUrl: string) => {
    if (previewUrls[previewKey] !== failedUrl) return;
    previewObjectUrlsRef.current.revoke(previewKey);
    setPreviewUrls((current) => { const next = { ...current }; delete next[previewKey]; return next; });
    previewRequestGateRef.current.invalidate(previewKey);
    setPreviewExpiries((current) => { const next = { ...current }; delete next[previewKey]; return next; });
    setPreviewLoading((current) => ({ ...current, [previewKey]: false }));
    setPreviewErrors((current) => ({ ...current, [previewKey]: '접근 권한이 없거나 이미지를 불러오지 못했습니다. 권한과 AssetVersion을 확인한 뒤 다시 시도해 주세요.' }));
  }, [previewUrls]);

  const runLocal = useCallback(async (draftId: string) => {
    const scope = captureScope();
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${base}/v1/photo-drafts/${encodeURIComponent(draftId)}/process-local?workspace_id=${encodeURIComponent(workspaceId)}`, {
        method: 'POST', headers: { ...headers, 'Idempotency-Key': `photo-${crypto.randomUUID()}` },
      });
      if (!response.ok) throw new Error(await responseError(response));
      if (!isScopeCurrent(scope)) return;
      await load();
      if (!isScopeCurrent(scope)) return;
    } catch (reason) {
      if (isScopeCurrent(scope)) setError(reason instanceof Error ? reason.message : '로컬 이미지 처리를 완료하지 못했습니다.');
    } finally { if (isScopeCurrent(scope)) setBusy(false); }
  }, [base, accessToken, workspaceId, load, captureScope, isScopeCurrent]);

  const reviewRun = useCallback(async (draftId: string, runId: string, action: 'approve' | 'request-changes' | 'reject') => {
    const scope = captureScope();
    if (reviewMutationInFlightRef.current || (action !== 'approve' && !reviewComment.trim())) return;
    reviewMutationInFlightRef.current = true;
    setBusy(true); setError(null); setManifestJson(null);
    try {
      const response = await fetch(`${base}/v1/photo-drafts/${encodeURIComponent(draftId)}/runs/${encodeURIComponent(runId)}/review/${action}?workspace_id=${encodeURIComponent(workspaceId)}`, {
        method: 'POST', headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ comment: reviewComment.trim() }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      if (!isScopeCurrent(scope)) return;
      setReviewComment('');
      await load();
    } catch (reason) {
      if (isScopeCurrent(scope)) setError(reason instanceof Error ? reason.message : 'Photo 결과 검수 상태를 변경하지 못했습니다.');
    } finally {
      if (isScopeCurrent(scope)) { reviewMutationInFlightRef.current = false; setBusy(false); }
    }
  }, [base, accessToken, workspaceId, reviewComment, load, captureScope, isScopeCurrent]);

  const exportRunManifest = useCallback(async (draftId: string, runId: string) => {
    if (reviewMutationInFlightRef.current) return;
    const scope = captureScope();
    reviewMutationInFlightRef.current = true;
    setBusy(true); setError(null);
    try {
      const response = await fetch(`${base}/v1/photo-drafts/${encodeURIComponent(draftId)}/runs/${encodeURIComponent(runId)}/export-manifest?workspace_id=${encodeURIComponent(workspaceId)}`, {
        method: 'POST', headers,
      });
      if (!response.ok) throw new Error(await responseError(response));
      const manifestResult = await response.json();
      if (!isScopeCurrent(scope)) return;
      setManifestJson(JSON.stringify(manifestResult, null, 2));
    } catch (reason) {
      if (isScopeCurrent(scope)) setError(reason instanceof Error ? reason.message : 'Photo 결과 manifest를 내보내지 못했습니다.');
    } finally {
      if (isScopeCurrent(scope)) { reviewMutationInFlightRef.current = false; setBusy(false); }
    }
  }, [base, accessToken, workspaceId, captureScope, isScopeCurrent]);

  const archiveDraft = useCallback(async (draftId: string) => {
    const scope = captureScope();
    if (reviewMutationInFlightRef.current) return;
    reviewMutationInFlightRef.current = true;
    setManifestJson(null); setReviewComment('');
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${base}/v1/photo-drafts/${encodeURIComponent(draftId)}/archive?workspace_id=${encodeURIComponent(workspaceId)}`, {
        method: 'POST', headers,
      });
      if (!response.ok) throw new Error(await responseError(response));
      if (!isScopeCurrent(scope)) return;
      await load();
      if (!isScopeCurrent(scope)) return;
    } catch (reason) {
      if (isScopeCurrent(scope)) setError(reason instanceof Error ? reason.message : 'Photo Draft를 보관하지 못했습니다.');
    } finally {
      if (isScopeCurrent(scope)) { reviewMutationInFlightRef.current = false; setBusy(false); }
    }
  }, [base, accessToken, workspaceId, load, captureScope, isScopeCurrent]);

  return (
    <section className="acs-photo-draft" aria-label="Photo Engine 준비 작업실">
      <header className="acs-photo-draft-header">
        <div><strong>Photo Engine 준비 작업실</strong><span>독립 2D 편집 작업 입력 준비</span></div>
        <label className={`acs-photo-upload${busy ? ' is-disabled' : ''}`}>
          이미지 추가
          <input type="file" accept="image/png,image/jpeg,image/webp,.png,.jpg,.jpeg,.webp" disabled={busy} onChange={uploadImage} />
        </label>
      </header>
      <fieldset className="acs-photo-rights" aria-label={RIGHTS_CONFIRMATION_COPY.heading} disabled={busy}>
        <legend>{RIGHTS_CONFIRMATION_COPY.heading}</legend>
        <label><input type="checkbox" checked={rightsConfirmed} onChange={event => setRightsConfirmed(event.currentTarget.checked)} /> {RIGHTS_CONFIRMATION_COPY.rightsConfirmed}</label>
        <label><input type="checkbox" checked={depictsPerson} onChange={event => { setDepictsPerson(event.currentTarget.checked); if (!event.currentTarget.checked) setLikenessConsent(false); }} /> {RIGHTS_CONFIRMATION_COPY.depictsPerson}</label>
        {depictsPerson && <label><input type="checkbox" checked={likenessConsent} onChange={event => setLikenessConsent(event.currentTarget.checked)} /> {RIGHTS_CONFIRMATION_COPY.likenessConsent}</label>}
      </fieldset>
      <p className="acs-photo-draft-notice">ENHANCE·LIGHTING은 Pillow 기반 결정론적 로컬 이미지 조정으로 실행할 수 있습니다(생성형 AI 아님). BACKGROUND·RETOUCH·COMPOSE는 AI 엔진 연결이 필요합니다. 로컬 조정은 인물 정체성·텍스트·로고 보존을 의미적으로 보증하지 않으며 결과 검수가 필요합니다. 승인 후 내보내는 manifest는 메타데이터 전용이며 게시·상업적 이용 권리를 부여하지 않습니다. Provider 호출과 크레딧 차감은 실행되지 않습니다.</p>
      {error && <p className="acs-photo-draft-error" role="alert">{error}</p>}
      <div className="acs-photo-draft-grid">
        <form className="acs-photo-draft-form" onSubmit={createDraft}>
          <AssetSourceTabs label="원본 이미지"
            mine={<label>원본 이미지
              <select value={sourceAssetId} onChange={(event) => setSourceAssetId(event.currentTarget.value)} disabled={busy || images.length === 0} required>
                <option value="">이미지를 선택하세요</option>
                {images.map((image) => <option key={image.asset_id} value={image.asset_id}>{image.original_filename}</option>)}
              </select>
            </label>}
            library={(done) => <LibraryBrowser apiBaseUrl={base} accessToken={accessToken}
              categories={['model', 'top', 'bottom', 'dress', 'outer', 'bag', 'hat', 'eyewear', 'shoes', 'jewelry', 'headwear', 'belt_scarf', 'background']}
              actionLabel="가져와서 선택" busyExternal={busy}
              onAction={async (item) => {
                try { const copy = await importLibraryItem(base, accessToken, item.item_id, workspaceId); await load(); setSourceAssetId(copy.asset_id); done(); }
                catch (reason) { setError(reason instanceof Error ? reason.message : '라이브러리에서 가져오지 못했습니다.'); }
              }}/>}
          />
          <label>편집 작업
            <select value={operation} onChange={(event) => setOperation(event.currentTarget.value as PhotoOperation)} disabled={busy}>
              <option value="ENHANCE">품질 향상</option><option value="BACKGROUND">배경 편집</option>
              <option value="LIGHTING">조명 조정</option><option value="RETOUCH">리터치</option>
              <option value="COMPOSE">합성 구성</option>
            </select>
          </label>
          <div className="acs-photo-draft-row">
            <label>출력 형식<select value={outputFormat} onChange={(event) => setOutputFormat(event.currentTarget.value as OutputFormat)} disabled={busy}>
              <option>PNG</option><option>JPEG</option><option>WEBP</option>
            </select></label>
            <label>출력 수량<input type="number" min={1} max={10} value={outputCount} onChange={(event) => setOutputCount(Number(event.currentTarget.value))} disabled={busy} /></label>
          </div>
          <label>스타일 메모<input value={targetStyle} maxLength={160} onChange={(event) => setTargetStyle(event.currentTarget.value)} placeholder="예: soft studio, natural daylight" disabled={busy} /></label>
          <label>편집 지시<textarea value={prompt} maxLength={1000} onChange={(event) => setPrompt(event.currentTarget.value)} rows={3} placeholder="원하는 편집 방향을 기록하세요." disabled={busy} /></label>
          <fieldset><legend>보존 조건</legend>
            <label><input type="checkbox" checked={preserveIdentity} onChange={(event) => setPreserveIdentity(event.currentTarget.checked)} disabled={busy} /> 인물 정체성 보존</label>
            <label><input type="checkbox" checked={preserveGeometry} onChange={(event) => setPreserveGeometry(event.currentTarget.checked)} disabled={busy} /> 제품 형태 보존</label>
            <label><input type="checkbox" checked={preserveText} onChange={(event) => setPreserveText(event.currentTarget.checked)} disabled={busy} /> 텍스트·로고 보존</label>
          </fieldset>
          <button type="submit" disabled={busy || !sourceAssetId}>Photo Draft 초안 저장</button>
        </form>
        <section className="acs-photo-draft-list" aria-label="저장된 Photo Draft">
          <header><strong>저장된 초안</strong><span>{drafts.length}개</span></header>
          {drafts.map((draft) => {
            const locallySupported = (draft.input.operation === 'ENHANCE' || draft.input.operation === 'LIGHTING')
              && draft.input.output_count === 1 && !draft.input.target_style && !draft.input.prompt;
            return <article key={draft.draft_id}>
              <div><strong>{draft.input.operation}</strong><span>{draft.input.output_format} · {draft.input.output_count}개 · {new Date(draft.created_at).toLocaleString()}</span>
                {draft.input.source_version_id && <><small>원본 고정 버전: {draft.input.source_version_id}</small><button type="button" disabled={busy || !!previewLoading[`${draft.input.source_asset_id}:${draft.input.source_version_id}`]} onClick={() => loadVersionPreview(draft.input.source_asset_id, draft.input.source_version_id!)}>{previewLoading[`${draft.input.source_asset_id}:${draft.input.source_version_id}`] ? '미리보기 불러오는 중…' : previewUrls[`${draft.input.source_asset_id}:${draft.input.source_version_id}`] ? '원본 미리보기 새로고침' : '원본 버전 미리보기 / 재시도'}</button>
                  {previewErrors[`${draft.input.source_asset_id}:${draft.input.source_version_id}`] && <small role="status">{previewErrors[`${draft.input.source_asset_id}:${draft.input.source_version_id}`]}</small>}
                  {previewExpiries[`${draft.input.source_asset_id}:${draft.input.source_version_id}`] && <small>링크 만료 예정: {new Date(previewExpiries[`${draft.input.source_asset_id}:${draft.input.source_version_id}`] * 1000).toLocaleTimeString()}</small>}
                  {previewUrls[`${draft.input.source_asset_id}:${draft.input.source_version_id}`] && <img className="acs-photo-preview" src={previewUrls[`${draft.input.source_asset_id}:${draft.input.source_version_id}`]} alt="Photo Draft 원본 immutable AssetVersion" loading="lazy" onError={(event) => handlePreviewImageError(`${draft.input.source_asset_id}:${draft.input.source_version_id}`, event.currentTarget.src)} />}</>}
                {locallySupported ? <button type="button" disabled={busy} onClick={() => runLocal(draft.draft_id)}>로컬 이미지 처리 실행</button>
                  : <small>현재 입력 조건은 AI Photo Engine 연결이 필요합니다.</small>}
                {(runsByDraft[draft.draft_id] || []).map((run) => <div className="acs-photo-run" key={run.run_id}>
                  <span>{run.status} · {run.operation} · 시도 {run.attempts}</span>
                  {run.output_asset_id && <><span>Output Asset: {run.output_asset_id} · Version: {run.output_version_id}</span><button type="button" disabled={busy || !run.output_version_id || !!previewLoading[`${run.output_asset_id}:${run.output_version_id}`]} onClick={() => loadVersionPreview(run.output_asset_id!, run.output_version_id!)}>{previewLoading[`${run.output_asset_id}:${run.output_version_id}`] ? '미리보기 불러오는 중…' : previewUrls[`${run.output_asset_id}:${run.output_version_id}`] ? '결과 미리보기 새로고침' : '결과 버전 미리보기 / 재시도'}</button>
                    {previewErrors[`${run.output_asset_id}:${run.output_version_id}`] && <small role="status">{previewErrors[`${run.output_asset_id}:${run.output_version_id}`]}</small>}
                    {previewExpiries[`${run.output_asset_id}:${run.output_version_id}`] && <small>링크 만료 예정: {new Date(previewExpiries[`${run.output_asset_id}:${run.output_version_id}`] * 1000).toLocaleTimeString()}</small>}
                    {previewUrls[`${run.output_asset_id}:${run.output_version_id}`] && <img className="acs-photo-preview" src={previewUrls[`${run.output_asset_id}:${run.output_version_id}`]} alt="Photo 처리 결과 immutable AssetVersion" loading="lazy" onError={(event) => handlePreviewImageError(`${run.output_asset_id}:${run.output_version_id}`, event.currentTarget.src)} />}</>}
                  {run.quality && <small>{run.quality.is_ai_generated ? 'AI 결과' : '비AI 로컬 조정'} · 의미 보존 검증: {run.quality.semantic_identity_preservation_verified ? '완료' : '미검증'}</small>}
                  {run.status === 'succeeded' && <><small>결과 검수 상태: {run.review_status || 'pending_review'}</small>
                    {!run.review_status || run.review_status === 'pending_review' || run.review_status === 'changes_requested' ? <div className="acs-photo-review-actions">
                      <button type="button" disabled={busy} onClick={() => reviewRun(draft.draft_id, run.run_id, 'approve')}>결과 승인</button>
                      <button type="button" disabled={busy || !reviewComment.trim()} onClick={() => reviewRun(draft.draft_id, run.run_id, 'request-changes')}>수정 요청</button>
                      <button type="button" disabled={busy || !reviewComment.trim()} onClick={() => reviewRun(draft.draft_id, run.run_id, 'reject')}>반려</button>
                    </div> : null}
                    {run.review_status === 'approved' ? <button type="button" disabled={busy} onClick={() => exportRunManifest(draft.draft_id, run.run_id)}>승인 결과 manifest 내보내기</button> : null}
                  </>}
                </div>)}
              </div>
              <button type="button" disabled={busy} onClick={() => archiveDraft(draft.draft_id)}>보관</button>
            </article>;
          })}
          {drafts.length === 0 && <p>저장된 초안이 없습니다.</p>}
          {drafts.some((draft) => (runsByDraft[draft.draft_id] || []).some((run) => run.status === 'succeeded' && (!run.review_status || run.review_status === 'pending_review' || run.review_status === 'changes_requested'))) && <label className="acs-photo-review-comment">결과 검수 의견<input value={reviewComment} maxLength={2000} onChange={(event) => setReviewComment(event.currentTarget.value)} disabled={busy} placeholder="수정 요청 또는 반려 사유를 입력하세요" /></label>}
          {manifestJson && <pre className="acs-photo-manifest">{manifestJson}</pre>}
        </section>
      </div>
    </section>
  );
}

export default PhotoDraftWorkspace;
