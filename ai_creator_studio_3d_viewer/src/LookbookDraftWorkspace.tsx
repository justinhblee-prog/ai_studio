import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import './LookbookDraftWorkspace.css';
import { useRequestScope } from './useRequestScope';
import { subscribeProjectLifecycleChanges } from './projectLifecycleEvents.mjs';
import { KeyedRequestGate } from './keyedRequestGate.mjs';
import { AuthenticatedPreviewObjectUrls } from './authenticatedPreviewObjectUrls.mjs';
import { getSignedDownloadExpiry, isSignedLinkUsable, isCurrentPreviewUrl } from './lookbookPreviewLinks.mjs';

type ImageAsset = { asset_id: string; original_filename: string };
type Project = { project_id: string; workspace_id: string; name: string; project_type: string; status: string; description: string | null; external_reference: string | null; created_by: string; created_at: string; updated_at: string };
type ProductVariant = { variant_id: string; product_id: string; workspace_id: string; sku: string; option_values: Record<string, string>; image_asset_ids: string[]; status: string; created_by: string; created_at: string; updated_at: string; archived_at?: string | null };
type Product = { product_id: string; workspace_id: string; sku: string; name: string; description: string | null; category: string; status: string; created_by: string; created_at: string; updated_at: string; archived_at?: string | null; image_asset_ids: string[]; variants: ProductVariant[] };
type Character = { character_id: string; identity: { name: string } };
type PhotoDraftRef = { draft_id: string; input: { title: string } };
type PhotoRunRef = { run_id: string; operation: string; status: string; review_status?: string | null; output_asset_id?: string | null; output_version_id?: string | null };
type ApprovedPhotoRun = PhotoRunRef & { photo_draft_id: string; photo_title: string };
type LookbookOutput = { output_item_id: string; draft_id: string; workspace_id: string; photo_run_id: string; asset_id: string; asset_version_id: string; provenance_id: string; checksum_sha256: string; product_id?: string | null; product_sku?: string | null; product_variant_id?: string | null; variant_sku?: string | null; variant_options: Record<string, string>; page_order: number; caption?: string | null; created_by: string; created_at: string };
type AssemblyReview = { draft_id: string; planning_status: string; status: 'no_outputs' | 'pending_review' | 'in_review' | 'approved' | 'rejected' | 'integrity_error'; output_count: number; snapshot_sha256: string | null; events: Array<{ event_id: string; actor_id: string; decision: string; comment: string; snapshot_sha256: string; output_count: number; created_at: string }> };
type PackageExport = { export_id: string; package_sha256: string; package_size_bytes: number; manifest_sha256: string; output_count: number; created_at: string; download_url: string; expires_at: number; internal_use_only: boolean; publication_authorized: boolean; commercial_rights_verified: boolean };
type PackageExportHistoryItem = { export_id: string; package_sha256: string; package_size_bytes: number; manifest_sha256: string; snapshot_sha256: string; output_count: number; created_at: string; expires_at: number; status: 'available' | 'expired' | 'missing' };
type OutputPreviewState = { status: 'loading' | 'ready' | 'error'; expiresAt: number | null; error: string | null };
type LookbookDraft = {
  draft_id: string;
  workspace_id: string;
  created_by: string;
  updated_at: string;
  archived_at?: string | null;
  status: 'draft' | 'archived';
  workflow_status: 'draft' | 'in_review' | 'changes_requested' | 'approved';
  created_at: string;
  input: {
    title: string;
    project_id?: string | null;
    character_id?: string | null;
    product_asset_ids: string[];
    product_ids: string[];
    product_variant_ids?: string[];
    person_asset_id?: string | null;
    scene_preset?: string | null;
    output_count: number;
  };
};

export type LookbookDraftWorkspaceProps = {
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

export function LookbookDraftWorkspace({ apiBaseUrl, accessToken, workspaceId }: LookbookDraftWorkspaceProps) {
  const base = apiBaseUrl.replace(/\/$/, '');
  const headers = { Authorization: `Bearer ${accessToken}` };
  const { capture: captureScope, isCurrent: isScopeCurrent } = useRequestScope([base, accessToken, workspaceId]);
  const [images, setImages] = useState<ImageAsset[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [productIds, setProductIds] = useState<string[]>([]);
  const [productVariantIds, setProductVariantIds] = useState<string[]>([]);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [drafts, setDrafts] = useState<LookbookDraft[]>([]);
  const [title, setTitle] = useState('New Lookbook');
  const [productAssetIds, setProductAssetIds] = useState<string[]>([]);
  const [personAssetId, setPersonAssetId] = useState('');
  const [projectId, setProjectId] = useState('');
  const [characterId, setCharacterId] = useState('');
  const [scenePreset, setScenePreset] = useState('minimal studio');
  const [outputCount, setOutputCount] = useState(4);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reviewComment, setReviewComment] = useState('');
  const [manifestJson, setManifestJson] = useState<string | null>(null);
  const [assemblyDraftId, setAssemblyDraftId] = useState<string | null>(null);
  const [approvedPhotoRuns, setApprovedPhotoRuns] = useState<ApprovedPhotoRun[]>([]);
  const [attachedOutputs, setAttachedOutputs] = useState<LookbookOutput[]>([]);
  const [outputPreviewUrls, setOutputPreviewUrls] = useState<Record<string, string>>({});
  const [outputPreviewStates, setOutputPreviewStates] = useState<Record<string, OutputPreviewState>>({});
  const [selectedPhotoRunId, setSelectedPhotoRunId] = useState('');
  const [selectedVariantId, setSelectedVariantId] = useState('');
  const [outputPageOrder, setOutputPageOrder] = useState(1);
  const [outputCaption, setOutputCaption] = useState('');
  const [outputManifestJson, setOutputManifestJson] = useState<string | null>(null);
  const [packageExport, setPackageExport] = useState<PackageExport | null>(null);
  const [packageExportHistory, setPackageExportHistory] = useState<PackageExportHistoryItem[]>([]);
  const [packageDownloadBusy, setPackageDownloadBusy] = useState(false);
  const [packageDownloadError, setPackageDownloadError] = useState<string | null>(null);
  const [assemblyReview, setAssemblyReview] = useState<AssemblyReview | null>(null);
  const [assemblyReviewComment, setAssemblyReviewComment] = useState('');
  const loadSequenceRef = useRef(0);
  const assemblyLoadRequestRef = useRef(0);
  const manifestRequestRef = useRef(0);
  const outputPreviewRequestGateRef = useRef(new KeyedRequestGate());
  const outputPreviewObjectUrlsRef = useRef(new AuthenticatedPreviewObjectUrls());
  const outputPreviewUrlRef = useRef<Record<string, string>>({});

  const clearAssemblyState = useCallback(() => {
    assemblyLoadRequestRef.current += 1;
    setAssemblyDraftId(null);
    setApprovedPhotoRuns([]);
    setAttachedOutputs([]);
    outputPreviewRequestGateRef.current.invalidateAll();
    outputPreviewObjectUrlsRef.current.clear();
    outputPreviewUrlRef.current = {};
    setOutputPreviewUrls({});
    setOutputPreviewStates({});
    setSelectedPhotoRunId('');
    setSelectedVariantId('');
    setOutputPageOrder(1);
    setOutputCaption('');
    setOutputManifestJson(null);
    setPackageExport(null);
    setPackageExportHistory([]);
    setPackageDownloadBusy(false);
    setPackageDownloadError(null);
    setAssemblyReview(null);
    setAssemblyReviewComment('');
  }, []);

  const load = useCallback(async (signal?: AbortSignal) => {
    const scope = captureScope();
    const requestId = ++loadSequenceRef.current;
    const [imageResponse, projectResponse, characterResponse, draftResponse, productResponse] = await Promise.all([
      fetch(`${base}/v1/assets?workspace_id=${encodeURIComponent(workspaceId)}&kind=image`, { headers, signal }),
      fetch(`${base}/v1/projects?workspace_id=${encodeURIComponent(workspaceId)}&status=ACTIVE`, { headers, signal }),
      fetch(`${base}/v1/workspaces/${encodeURIComponent(workspaceId)}/characters`, { headers, signal }),
      fetch(`${base}/v1/lookbook-drafts?workspace_id=${encodeURIComponent(workspaceId)}&limit=100`, { headers, signal }),
      fetch(`${base}/v1/products?workspace_id=${encodeURIComponent(workspaceId)}&limit=100`, { headers, signal }),
    ]);
    if (signal?.aborted || !isScopeCurrent(scope) || requestId !== loadSequenceRef.current) return;
    for (const response of [imageResponse, projectResponse, characterResponse, draftResponse, productResponse]) {
      if (!response.ok) throw new Error(await responseError(response));
    }
    const imageResult = await imageResponse.json() as { items: ImageAsset[] };
    const projectResult = await projectResponse.json() as { items: Project[] };
    const characterResult = await characterResponse.json() as { items: Character[] };
    const draftResult = await draftResponse.json() as { items: LookbookDraft[] };
    const productResult = await productResponse.json() as { items: Product[] };
    if (signal?.aborted || !isScopeCurrent(scope) || requestId !== loadSequenceRef.current) return;
    setImages(imageResult.items);
    setProjects(projectResult.items);
    setProjectId((current) => projectResult.items.some((project) => project.project_id === current) ? current : '');
    setCharacters(characterResult.items);
    setDrafts(draftResult.items);
    setProducts(productResult.items);
    setProductIds((current) => current.filter((id) => productResult.items.some((item) => item.product_id === id)));
    setProductVariantIds((current) => current.filter((id) => productResult.items.some((item) => item.variants.some((variant) => variant.variant_id === id && variant.status === 'active'))));
    setProductAssetIds((current) => { const valid = current.filter((id) => imageResult.items.some((item) => item.asset_id === id)); return valid.length ? valid : imageResult.items[0]?.asset_id ? [imageResult.items[0].asset_id] : []; });
  }, [base, accessToken, workspaceId, captureScope, isScopeCurrent]);

  useEffect(() => {
    setImages([]); setProjects([]); setProducts([]); setCharacters([]); setDrafts([]);
    setProductIds([]); setProductVariantIds([]); setProductAssetIds([]); setPersonAssetId(''); setProjectId(''); setCharacterId('');
    manifestRequestRef.current += 1;
    setManifestJson(null);
    clearAssemblyState();
    setError(null); setBusy(false);
    setTitle('New Lookbook'); setScenePreset('minimal studio'); setOutputCount(4); setReviewComment('');
  }, [base, accessToken, workspaceId, clearAssemblyState]);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Lookbook 자료를 불러오지 못했습니다.');
    });
    return () => controller.abort();
  }, [load]);

  useEffect(() => subscribeProjectLifecycleChanges((change) => {
    if (change.workspaceId !== workspaceId) return;
    load().catch((reason: unknown) => setError(reason instanceof Error ? reason.message : '프로젝트 상태 변경을 반영하지 못했습니다.'));
  }), [workspaceId, load]);

  const createDraft = useCallback(async (event: FormEvent<HTMLFormElement>) => {
    const scope = captureScope();
    event.preventDefault();
    if (productAssetIds.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${base}/v1/lookbook-drafts`, {
        method: 'POST', headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: workspaceId,
          title: title.trim(),
          project_id: projectId || null,
          character_id: characterId || null,
          product_asset_ids: productAssetIds,
          product_ids: productIds,
          product_variant_ids: productVariantIds,
          person_asset_id: personAssetId || null,
          scene_preset: scenePreset.trim() || null,
          output_count: outputCount,
        }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      if (!isScopeCurrent(scope)) return;
      await load();
      if (!isScopeCurrent(scope)) return;
    } catch (reason) {
      if (isScopeCurrent(scope)) setError(reason instanceof Error ? reason.message : 'Lookbook 초안을 저장하지 못했습니다.');
    } finally {
      if (isScopeCurrent(scope)) setBusy(false);
    }
  }, [base, accessToken, workspaceId, title, projectId, characterId, productAssetIds, productIds, productVariantIds, personAssetId, scenePreset, outputCount, load, captureScope, isScopeCurrent]);

  const reviewAction = useCallback(async (draftId: string, action: 'submit' | 'approve' | 'request-changes') => {
    const scope = captureScope();
    setBusy(true); setError(null); setManifestJson(null);
    try {
      const response = await fetch(`${base}/v1/lookbook-drafts/${encodeURIComponent(draftId)}/${action}?workspace_id=${encodeURIComponent(workspaceId)}`, {
        method: 'POST', headers: action === 'submit' ? headers : { ...headers, 'Content-Type': 'application/json' },
        ...(action === 'submit' ? {} : { body: JSON.stringify({ comment: action === 'request-changes' ? reviewComment.trim() : null }) }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      if (!isScopeCurrent(scope)) return;
      await load();
      if (!isScopeCurrent(scope)) return;
    } catch (reason) { if (isScopeCurrent(scope)) setError(reason instanceof Error ? reason.message : '검토 상태를 변경하지 못했습니다.'); }
    finally { if (isScopeCurrent(scope)) setBusy(false); }
  }, [base, accessToken, workspaceId, reviewComment, load, captureScope, isScopeCurrent]);

  const showManifest = useCallback(async (draftId: string) => {
    const scope = captureScope();
    const requestId = ++manifestRequestRef.current;
    const isManifestRequestCurrent = () => requestId === manifestRequestRef.current && isScopeCurrent(scope);
    setBusy(true); setError(null);
    try {
      const response = await fetch(`${base}/v1/lookbook-drafts/${encodeURIComponent(draftId)}/manifest?workspace_id=${encodeURIComponent(workspaceId)}`, { headers });
      if (!response.ok) throw new Error(await responseError(response));
      if (!isManifestRequestCurrent()) return;
      const manifestResult = await response.json();
      if (!isManifestRequestCurrent()) return;
      setManifestJson(JSON.stringify(manifestResult, null, 2));
    } catch (reason) { if (isManifestRequestCurrent()) setError(reason instanceof Error ? reason.message : '승인된 기획안 manifest를 불러오지 못했습니다.'); }
    finally { if (isManifestRequestCurrent()) setBusy(false); }
  }, [base, accessToken, workspaceId, captureScope, isScopeCurrent]);

  useEffect(() => () => outputPreviewObjectUrlsRef.current.clear(), []);

  const requestOutputPreview = useCallback(async (item: LookbookOutput) => {
    const scope = captureScope();
    const outputId = item.output_item_id;
    const requestId = outputPreviewRequestGateRef.current.next(outputId);
    const isCurrent = () => outputPreviewRequestGateRef.current.isCurrent(outputId, requestId) && isScopeCurrent(scope);
    outputPreviewObjectUrlsRef.current.revoke(outputId);
    outputPreviewUrlRef.current[outputId] = '';
    setOutputPreviewUrls((current) => ({ ...current, [outputId]: '' }));
    setOutputPreviewStates((current) => ({ ...current, [outputId]: { status: 'loading', expiresAt: null, error: null } }));
    try {
      const response = await fetch(`${base}/v1/assets/${encodeURIComponent(item.asset_id)}/versions/${encodeURIComponent(item.asset_version_id)}/preview-content`, { headers });
      if (!response.ok) throw new Error(await responseError(response));
      const previewBlob = await response.blob();
      if (!isCurrent()) return;
      const resolvedUrl = outputPreviewObjectUrlsRef.current.replace(outputId, previewBlob);
      outputPreviewUrlRef.current[outputId] = resolvedUrl;
      setOutputPreviewUrls((current) => ({ ...current, [outputId]: resolvedUrl }));
      setOutputPreviewStates((current) => ({ ...current, [outputId]: { status: 'ready', expiresAt: null, error: null } }));
    } catch (reason) {
      if (!isCurrent()) return;
      outputPreviewUrlRef.current[outputId] = '';
      setOutputPreviewUrls((current) => ({ ...current, [outputId]: '' }));
      setOutputPreviewStates((current) => ({ ...current, [outputId]: { status: 'error', expiresAt: null, error: reason instanceof Error ? reason.message : '미리보기 링크를 발급하지 못했습니다.' } }));
    }
  }, [base, accessToken, captureScope, isScopeCurrent]);

  const loadOutputAssembly = useCallback(async (draftId: string) => {
    const scope = captureScope();
    const requestId = ++assemblyLoadRequestRef.current;
    const isAssemblyRequestCurrent = () => requestId === assemblyLoadRequestRef.current && isScopeCurrent(scope);
    setBusy(true); setError(null); setOutputManifestJson(null); setPackageExport(null); setPackageExportHistory([]); setPackageDownloadError(null);
    outputPreviewRequestGateRef.current.invalidateAll();
    outputPreviewObjectUrlsRef.current.clear();
    outputPreviewUrlRef.current = {};
    setOutputPreviewUrls({}); setOutputPreviewStates({}); setAttachedOutputs([]); setApprovedPhotoRuns([]); setAssemblyReview(null);
    setAssemblyDraftId(draftId);
    try {
      const [photoDraftResponse, outputResponse, reviewResponse, exportHistoryResponse] = await Promise.all([
        fetch(`${base}/v1/photo-drafts?workspace_id=${encodeURIComponent(workspaceId)}&limit=100`, { headers }),
        fetch(`${base}/v1/lookbook-drafts/${encodeURIComponent(draftId)}/outputs?workspace_id=${encodeURIComponent(workspaceId)}`, { headers }),
        fetch(`${base}/v1/lookbook-drafts/${encodeURIComponent(draftId)}/outputs/review?workspace_id=${encodeURIComponent(workspaceId)}`, { headers }),
        fetch(`${base}/v1/lookbook-drafts/${encodeURIComponent(draftId)}/outputs/exports?workspace_id=${encodeURIComponent(workspaceId)}`, { headers }),
      ]);
      if (!photoDraftResponse.ok) throw new Error(await responseError(photoDraftResponse));
      if (!outputResponse.ok) throw new Error(await responseError(outputResponse));
      if (!reviewResponse.ok) throw new Error(await responseError(reviewResponse));
      if (!exportHistoryResponse.ok) throw new Error(await responseError(exportHistoryResponse));
      const photoDrafts = await photoDraftResponse.json() as { items: PhotoDraftRef[] };
      const outputResult = await outputResponse.json() as { items: LookbookOutput[] };
      const reviewResult = await reviewResponse.json() as AssemblyReview;
      const exportHistoryResult = await exportHistoryResponse.json() as { items: PackageExportHistoryItem[]; total: number };
      if (!isAssemblyRequestCurrent()) return;
      outputPreviewRequestGateRef.current.invalidateAll();
      outputPreviewUrlRef.current = {};
      setOutputPreviewUrls({});
      setOutputPreviewStates(Object.fromEntries(outputResult.items.map((item): [string, OutputPreviewState] => [item.output_item_id, { status: 'loading', expiresAt: null, error: null }])));
      if (!isAssemblyRequestCurrent()) return;
      await Promise.all(outputResult.items.map((item) => requestOutputPreview(item)));
      if (!isAssemblyRequestCurrent()) return;
      const runGroups = await Promise.all(photoDrafts.items.map(async (photoDraft) => {
        const response = await fetch(`${base}/v1/photo-drafts/${encodeURIComponent(photoDraft.draft_id)}/runs?workspace_id=${encodeURIComponent(workspaceId)}&limit=100`, { headers });
        if (!response.ok) return [] as ApprovedPhotoRun[];
        const result = await response.json() as { items: PhotoRunRef[] };
        return result.items.filter((run) => run.status === 'succeeded' && run.review_status === 'approved' && run.output_asset_id && run.output_version_id)
          .map((run) => ({ ...run, photo_draft_id: photoDraft.draft_id, photo_title: photoDraft.input.title }));
      }));
      if (!isAssemblyRequestCurrent()) return;
      setApprovedPhotoRuns(runGroups.flat());
      setAttachedOutputs(outputResult.items);

      setAssemblyReview(reviewResult);
      setPackageExportHistory(exportHistoryResult.items);
      setAssemblyReviewComment('');
      setSelectedPhotoRunId(''); setSelectedVariantId('');
      setOutputPageOrder(outputResult.items.length + 1); setOutputCaption('');
      setAssemblyDraftId(draftId);
    } catch (reason) {
      if (isAssemblyRequestCurrent()) setError(reason instanceof Error ? reason.message : '승인된 Photo 결과를 불러오지 못했습니다.');
    } finally { if (isAssemblyRequestCurrent()) setBusy(false); }
  }, [base, accessToken, workspaceId, captureScope, isScopeCurrent, requestOutputPreview]);

  const attachPhotoOutput = useCallback(async () => {
    const scope = captureScope();
    if (!assemblyDraftId || !selectedPhotoRunId) return;
    setBusy(true); setError(null); setOutputManifestJson(null);
    try {
      const response = await fetch(`${base}/v1/lookbook-drafts/${encodeURIComponent(assemblyDraftId)}/outputs?workspace_id=${encodeURIComponent(workspaceId)}`, {
        method: 'POST', headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ photo_run_id: selectedPhotoRunId, product_variant_id: selectedVariantId || null,
          page_order: outputPageOrder, caption: outputCaption.trim() || null }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      if (!isScopeCurrent(scope)) return;
      await loadOutputAssembly(assemblyDraftId);
      if (!isScopeCurrent(scope)) return;
    } catch (reason) { if (isScopeCurrent(scope)) setError(reason instanceof Error ? reason.message : 'Photo 결과를 Lookbook에 연결하지 못했습니다.'); }
    finally { if (isScopeCurrent(scope)) setBusy(false); }
  }, [base, accessToken, workspaceId, assemblyDraftId, selectedPhotoRunId, selectedVariantId, outputPageOrder, outputCaption, loadOutputAssembly, captureScope, isScopeCurrent]);

  const submitOutputAssembly = useCallback(async () => {
    const scope = captureScope();
    if (!assemblyDraftId) return;
    setBusy(true); setError(null); setOutputManifestJson(null);
    try {
      const response = await fetch(`${base}/v1/lookbook-drafts/${encodeURIComponent(assemblyDraftId)}/outputs/submit?workspace_id=${encodeURIComponent(workspaceId)}`, { method: 'POST', headers });
      if (!response.ok) throw new Error(await responseError(response));
      if (!isScopeCurrent(scope)) return;
      await loadOutputAssembly(assemblyDraftId);
      if (!isScopeCurrent(scope)) return;
    } catch (reason) { if (isScopeCurrent(scope)) setError(reason instanceof Error ? reason.message : 'Lookbook 조립 검토를 요청하지 못했습니다.'); }
    finally { if (isScopeCurrent(scope)) setBusy(false); }
  }, [base, accessToken, workspaceId, assemblyDraftId, loadOutputAssembly, captureScope, isScopeCurrent]);

  const decideOutputAssembly = useCallback(async (decision: 'approve' | 'reject') => {
    const scope = captureScope();
    if (!assemblyDraftId || (decision === 'reject' && !assemblyReviewComment.trim())) return;
    setBusy(true); setError(null); setOutputManifestJson(null);
    try {
      const response = await fetch(`${base}/v1/lookbook-drafts/${encodeURIComponent(assemblyDraftId)}/outputs/${decision}?workspace_id=${encodeURIComponent(workspaceId)}`, {
        method: 'POST', headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ comment: assemblyReviewComment.trim() }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      if (!isScopeCurrent(scope)) return;
      await loadOutputAssembly(assemblyDraftId);
      if (!isScopeCurrent(scope)) return;
    } catch (reason) { if (isScopeCurrent(scope)) setError(reason instanceof Error ? reason.message : 'Lookbook 조립 검토를 완료하지 못했습니다.'); }
    finally { if (isScopeCurrent(scope)) setBusy(false); }
  }, [base, accessToken, workspaceId, assemblyDraftId, assemblyReviewComment, loadOutputAssembly, captureScope, isScopeCurrent]);

  const createPackageExport = useCallback(async () => {
    const scope = captureScope();
    if (!assemblyDraftId || assemblyReview?.status !== 'approved') return;
    setBusy(true); setError(null); setPackageDownloadError(null);
    try {
      const response = await fetch(`${base}/v1/lookbook-drafts/${encodeURIComponent(assemblyDraftId)}/outputs/package-export?workspace_id=${encodeURIComponent(workspaceId)}`, { method: 'POST', headers });
      if (!response.ok) throw new Error(await responseError(response));
      if (!isScopeCurrent(scope)) return;
      const result = await response.json() as PackageExport;
      if (!isScopeCurrent(scope)) return;
      setPackageExport({ ...result, download_url: new URL(result.download_url, base).toString() });
      const historyResponse = await fetch(`${base}/v1/lookbook-drafts/${encodeURIComponent(assemblyDraftId)}/outputs/exports?workspace_id=${encodeURIComponent(workspaceId)}`, { headers });
      if (!historyResponse.ok) throw new Error(await responseError(historyResponse));
      const historyResult = await historyResponse.json() as { items: PackageExportHistoryItem[] };
      if (isScopeCurrent(scope)) setPackageExportHistory(historyResult.items);
    } catch (reason) { if (isScopeCurrent(scope)) setError(reason instanceof Error ? reason.message : '내부 Lookbook ZIP을 만들지 못했습니다.'); }
    finally { if (isScopeCurrent(scope)) setBusy(false); }
  }, [base, accessToken, workspaceId, assemblyDraftId, assemblyReview, captureScope, isScopeCurrent]);

  const downloadPackageExport = useCallback(async () => {
    const scope = captureScope();
    const isCurrent = () => isScopeCurrent(scope);
    if (!packageExport || !isCurrent()) return;
    const signedExpiry = getSignedDownloadExpiry(packageExport.download_url, base);
    if (!isSignedLinkUsable(signedExpiry)) {
      setPackageDownloadError('다운로드 서명 링크가 만료되었습니다. 새 내부 ZIP을 생성해 새 링크를 발급해 주세요.');
      return;
    }
    setPackageDownloadBusy(true);
    setPackageDownloadError(null);
    try {
      const response = await fetch(packageExport.download_url, { method: 'GET', headers, cache: 'no-store' });
      if (!response.ok) throw new Error(await responseError(response));
      const blob = await response.blob();
      if (!isCurrent()) return;
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = objectUrl;
      anchor.download = `lookbook-${assemblyDraftId || packageExport.export_id}.zip`;
      anchor.style.display = 'none';
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    } catch (reason) {
      if (isCurrent()) setPackageDownloadError(reason instanceof Error ? reason.message : 'ZIP 다운로드에 실패했습니다. 서명 링크가 만료되었을 수 있습니다.');
    } finally {
      if (isCurrent()) setPackageDownloadBusy(false);
    }
  }, [base, packageExport, assemblyDraftId, captureScope, isScopeCurrent]);

  const exportOutputManifest = useCallback(async () => {
    const scope = captureScope();
    if (!assemblyDraftId || assemblyReview?.status !== 'approved') return;
    setBusy(true); setError(null);
    try {
      const response = await fetch(`${base}/v1/lookbook-drafts/${encodeURIComponent(assemblyDraftId)}/outputs/manifest?workspace_id=${encodeURIComponent(workspaceId)}`, { method: 'POST', headers });
      if (!response.ok) throw new Error(await responseError(response));
      if (!isScopeCurrent(scope)) return;
      const manifestResult = await response.json();
      if (!isScopeCurrent(scope)) return;
      setOutputManifestJson(JSON.stringify(manifestResult, null, 2));
    } catch (reason) { if (isScopeCurrent(scope)) setError(reason instanceof Error ? reason.message : 'Lookbook 결과 manifest를 만들지 못했습니다.'); }
    finally { if (isScopeCurrent(scope)) setBusy(false); }
  }, [base, accessToken, workspaceId, assemblyDraftId, assemblyReview, captureScope, isScopeCurrent]);

  const archiveDraft = useCallback(async (draftId: string) => {
    const scope = captureScope();
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${base}/v1/lookbook-drafts/${encodeURIComponent(draftId)}/archive?workspace_id=${encodeURIComponent(workspaceId)}`, { method: 'POST', headers });
      if (!response.ok) throw new Error(await responseError(response));
      if (!isScopeCurrent(scope)) return;
      manifestRequestRef.current += 1;
      setManifestJson(null);
      if (assemblyDraftId === draftId) clearAssemblyState();
      await load();
      if (!isScopeCurrent(scope)) return;
    } catch (reason) {
      if (isScopeCurrent(scope)) setError(reason instanceof Error ? reason.message : 'Lookbook 초안을 보관하지 못했습니다.');
    } finally {
      if (isScopeCurrent(scope)) setBusy(false);
    }
  }, [base, accessToken, workspaceId, assemblyDraftId, load, clearAssemblyState, captureScope, isScopeCurrent]);

  const assemblyDraft = drafts.find((draft) => draft.draft_id === assemblyDraftId);
  const assemblyEditable = assemblyReview?.status === 'pending_review' || assemblyReview?.status === 'no_outputs';

  return (
    <section className="acs-lookbook-draft" aria-label="Lookbook 준비 작업실">
      <header><div><strong>Lookbook 준비 작업실</strong><span>상품·모델·장면 구성</span></div></header>
      <p className="acs-lookbook-notice">Lookbook 기획안 검토·승인과 개별 승인된 Photo 결과 AssetVersion 연결을 지원합니다. 새로운 사진 생성/AI Provider 호출, 바이너리 ZIP 내보내기, 게시·상업 권리 승인은 실행되지 않습니다. 결과 manifest는 내부 메타데이터만 포함하며 조립 순서는 별도 검토·승인 후에만 내보낼 수 있습니다.</p>
      {error && <p className="acs-lookbook-error" role="alert">{error}</p>}
      <div className="acs-lookbook-grid">
        <form onSubmit={createDraft}>
          <label>초안 이름<input value={title} maxLength={120} onChange={(event) => setTitle(event.currentTarget.value)} disabled={busy} required /></label>
          <label>카탈로그 상품<select multiple size={4} value={productIds} onChange={(event) => setProductIds(Array.from(event.currentTarget.selectedOptions, (option) => option.value))} disabled={busy || products.length === 0}>
            {products.map((product) => <option key={product.product_id} value={product.product_id}>{product.sku} · {product.name}</option>)}
          </select><small>{productIds.length}개 카탈로그 상품 선택</small></label>
          <label>상품 옵션 / Variant<select multiple size={4} value={productVariantIds} onChange={(event) => setProductVariantIds(Array.from(event.currentTarget.selectedOptions, (option) => option.value))} disabled={busy || products.every((product) => product.variants.filter((variant) => variant.status === 'active').length === 0)}>
            {products.flatMap((product) => product.variants.filter((variant) => variant.status === 'active').map((variant) => <option key={variant.variant_id} value={variant.variant_id}>{variant.sku} · {product.name} · {Object.entries(variant.option_values).map(([key, value]) => `${key}: ${value}`).join(' / ')}</option>))}
          </select><small>{productVariantIds.length}개 SKU 옵션 선택 · 옵션 이미지가 없으면 상품 대표/갤러리 이미지 사용</small></label>
          <label>직접 상품 이미지(선택)<select multiple size={4} value={productAssetIds} onChange={(event) => { const selected = Array.from(event.currentTarget.selectedOptions, (option) => option.value); setProductAssetIds(selected); if (personAssetId && selected.includes(personAssetId)) setPersonAssetId(''); }} disabled={busy || images.length === 0}>
            {images.map((item) => <option key={item.asset_id} value={item.asset_id}>{item.original_filename}</option>)}
          </select><small>여러 상품 이미지를 선택할 수 있습니다. {productAssetIds.length}개 선택됨</small></label>
          <label>인물 이미지(선택)<select value={personAssetId} onChange={(event) => setPersonAssetId(event.currentTarget.value)} disabled={busy}>
            <option value="">선택 안 함</option>{images.filter((item) => !productAssetIds.includes(item.asset_id) && !products.filter((product) => productIds.includes(product.product_id)).some((product) => product.image_asset_ids.includes(item.asset_id))).map((item) => <option key={item.asset_id} value={item.asset_id}>{item.original_filename}</option>)}
          </select></label>
          <label>프로젝트<select value={projectId} onChange={(event) => setProjectId(event.currentTarget.value)} disabled={busy}>
            <option value="">프로젝트 연결 안 함</option>{projects.map((item) => <option key={item.project_id} value={item.project_id}>{item.name}</option>)}
          </select></label>
          <label>캐릭터<select value={characterId} onChange={(event) => setCharacterId(event.currentTarget.value)} disabled={busy}>
            <option value="">캐릭터 연결 안 함</option>{characters.map((item) => <option key={item.character_id} value={item.character_id}>{item.identity.name}</option>)}
          </select></label>
          <div className="acs-lookbook-row">
            <label>장면 프리셋<input value={scenePreset} maxLength={120} onChange={(event) => setScenePreset(event.currentTarget.value)} disabled={busy} /></label>
            <label>결과 수량<input type="number" min={1} max={20} value={outputCount} onChange={(event) => setOutputCount(Number(event.currentTarget.value))} disabled={busy} /></label>
          </div>
          <button type="submit" disabled={busy || (productAssetIds.length === 0 && productIds.length === 0 && productVariantIds.length === 0)}>Lookbook 초안 저장</button>
        </form>
        <section className="acs-lookbook-list" aria-label="저장된 Lookbook 초안">
          <header><strong>저장된 초안</strong><span>{drafts.length}개</span></header>
          {drafts.map((draft) => <article key={draft.draft_id} className="acs-lookbook-item">
            <div><strong>{draft.input.title}</strong><span>{draft.input.product_ids.length + (draft.input.product_variant_ids?.length || 0) + draft.input.product_asset_ids.length}개 상품 참조 · {draft.input.output_count}개 결과 예정 · {draft.input.scene_preset || '장면 미지정'}</span><span>기획 검토 상태: {draft.workflow_status}</span>
              <div className="acs-lookbook-actions">
                {draft.workflow_status === 'draft' || draft.workflow_status === 'changes_requested' ? <button type="button" disabled={busy} onClick={() => reviewAction(draft.draft_id, 'submit')}>검토 요청</button> : null}
                {draft.workflow_status === 'in_review' ? <><button type="button" disabled={busy} onClick={() => reviewAction(draft.draft_id, 'approve')}>기획 승인</button><button type="button" disabled={busy || !reviewComment.trim()} onClick={() => reviewAction(draft.draft_id, 'request-changes')}>수정 요청</button></> : null}
                {draft.workflow_status === 'approved' ? <><button type="button" disabled={busy} onClick={() => showManifest(draft.draft_id)}>승인 기획 manifest 보기</button><button type="button" disabled={busy} onClick={() => loadOutputAssembly(draft.draft_id)}>승인 Photo 결과 연결</button></> : null}
                <button type="button" disabled={busy} onClick={() => archiveDraft(draft.draft_id)}>보관</button>
              </div>
            </div>
          </article>)}
          {drafts.length === 0 && <p>저장된 Lookbook 초안이 없습니다.</p>}
          {assemblyDraftId && <section className="acs-lookbook-output-assembly" aria-label="승인된 Photo 결과 조립">
            <header><strong>승인된 Photo 결과 조립</strong><button type="button" disabled={busy} onClick={clearAssemblyState}>닫기</button></header>
            <p>개별 승인된 Photo AssetVersion만 연결합니다. 연결을 마친 뒤 조립 순서를 별도로 검토·승인해야 내부 manifest를 내보낼 수 있습니다.</p>
            <label>승인된 Photo 결과<select value={selectedPhotoRunId} onChange={(event) => setSelectedPhotoRunId(event.currentTarget.value)} disabled={busy || !assemblyEditable || approvedPhotoRuns.length === 0}>
              <option value="">결과 선택</option>{approvedPhotoRuns.map((run) => <option key={run.run_id} value={run.run_id}>{run.photo_title} · {run.operation} · {run.output_asset_id} · {run.run_id}</option>)}
            </select></label>
            <label>상품 Variant 연결(선택)<select value={selectedVariantId} onChange={(event) => setSelectedVariantId(event.currentTarget.value)} disabled={busy || !assemblyEditable}>
              <option value="">상품 미연결</option>{products.flatMap((product) => product.variants.filter((variant) => variant.status === 'active' && (assemblyDraft?.input.product_variant_ids?.includes(variant.variant_id) || assemblyDraft?.input.product_ids.includes(product.product_id))).map((variant) => <option key={variant.variant_id} value={variant.variant_id}>{product.sku} · {variant.sku}</option>))}
            </select></label>
            <div className="acs-lookbook-row"><label>페이지 순서<input type="number" min={1} max={100} value={outputPageOrder} onChange={(event) => setOutputPageOrder(Number(event.currentTarget.value))} disabled={busy || !assemblyEditable} /></label>
              <label>캡션<input value={outputCaption} maxLength={240} onChange={(event) => setOutputCaption(event.currentTarget.value)} disabled={busy || !assemblyEditable} /></label></div>
            <button type="button" disabled={busy || !assemblyEditable || !selectedPhotoRunId || outputPageOrder < 1 || outputPageOrder > 100} onClick={attachPhotoOutput}>Photo 결과 연결</button>
            <div className="acs-lookbook-output-items">{attachedOutputs.map((item) => <article key={item.output_item_id}><strong>#{item.page_order} · {item.variant_sku || item.product_sku || '상품 미연결'}</strong><span>Asset {item.asset_id} · Version {item.asset_version_id}</span>{outputPreviewUrls[item.output_item_id] && <img className="acs-lookbook-output-preview" src={outputPreviewUrls[item.output_item_id]} alt={`Lookbook page ${item.page_order} exact AssetVersion preview`} loading="lazy" onError={() => { const failedUrl = outputPreviewUrls[item.output_item_id]; if (!isCurrentPreviewUrl(outputPreviewUrlRef.current[item.output_item_id], failedUrl)) return; outputPreviewObjectUrlsRef.current.revoke(item.output_item_id); outputPreviewRequestGateRef.current.invalidate(item.output_item_id); outputPreviewUrlRef.current[item.output_item_id] = ''; setOutputPreviewUrls((current) => current[item.output_item_id] === failedUrl ? { ...current, [item.output_item_id]: '' } : current); setOutputPreviewStates((current) => current[item.output_item_id]?.status === 'ready' ? { ...current, [item.output_item_id]: { status: 'error', expiresAt: null, error: '접근 권한이 없거나 이미지를 불러오지 못했습니다.' } } : current); }} />}{outputPreviewStates[item.output_item_id]?.status === 'loading' && <small>정확한 AssetVersion 미리보기 링크 발급 중…</small>}{outputPreviewStates[item.output_item_id]?.status === 'error' && <small role="alert">미리보기 오류: {outputPreviewStates[item.output_item_id].error}</small>}{outputPreviewStates[item.output_item_id]?.expiresAt && <small>미리보기 링크 만료: {new Date(outputPreviewStates[item.output_item_id].expiresAt! * 1000).toLocaleString()}</small>}{outputPreviewStates[item.output_item_id]?.status !== 'loading' && <button type="button" disabled={busy} onClick={() => requestOutputPreview(item)}>미리보기 새로고침 / 재시도</button>}<small>{item.caption || '캡션 없음'} · {Object.entries(item.variant_options).map(([key, value]) => `${key}: ${value}`).join(' / ')}</small></article>)}
              {attachedOutputs.length === 0 && <p>아직 연결된 승인 Photo 결과가 없습니다.</p>}</div>
            <div className="acs-lookbook-assembly-review"><strong>조립 검토 상태: {assemblyReview?.status || '불러오는 중'}</strong>
              {assemblyReview?.status === 'pending_review' ? <button type="button" disabled={busy || attachedOutputs.length === 0} onClick={submitOutputAssembly}>조립 검토 요청</button> : null}
              {assemblyReview?.status === 'in_review' ? <><label>반려 의견<input value={assemblyReviewComment} maxLength={2000} onChange={(event) => setAssemblyReviewComment(event.currentTarget.value)} disabled={busy} placeholder="반려 사유를 입력하세요" /></label><div><button type="button" disabled={busy} onClick={() => decideOutputAssembly('approve')}>조립 승인</button><button type="button" disabled={busy || !assemblyReviewComment.trim()} onClick={() => decideOutputAssembly('reject')}>조립 반려</button></div></> : null}
              {assemblyReview?.status === 'rejected' ? <small>조립은 반려되어 수정할 수 없습니다. 변경된 순서는 새 Lookbook 초안에서 구성하세요.</small> : null}
              {assemblyReview?.status === 'integrity_error' ? <small>조립 snapshot 또는 Photo AssetVersion 무결성 검증에 실패했습니다.</small> : null}
            </div>
            <button type="button" disabled={busy || assemblyReview?.status !== 'approved'} onClick={exportOutputManifest}>승인된 Lookbook 결과 manifest 내보내기</button>
            {outputManifestJson && <pre className="acs-lookbook-manifest">{outputManifestJson}</pre>}
            <button type="button" disabled={busy || assemblyReview?.status !== 'approved'} onClick={createPackageExport}>승인된 Lookbook 내부 ZIP 만들기</button>
            {packageExport && <div className="acs-lookbook-package-download"><button type="button" disabled={packageDownloadBusy} onClick={downloadPackageExport}>{packageDownloadBusy ? 'ZIP 다운로드 중…' : 'Lookbook ZIP 다운로드'}</button><small>{(packageExport.package_size_bytes / 1024).toFixed(1)} KB · SHA-256 {packageExport.package_sha256}</small><small>다운로드 서명 링크 만료: {getSignedDownloadExpiry(packageExport.download_url, base) ? new Date(getSignedDownloadExpiry(packageExport.download_url, base)! * 1000).toLocaleString() : '확인할 수 없음'} · 보관 만료: {new Date(packageExport.expires_at * 1000).toLocaleString()}</small>{packageDownloadError && <small role="alert">{packageDownloadError}</small>}<button type="button" disabled={busy || packageDownloadBusy || assemblyReview?.status !== 'approved'} onClick={createPackageExport}>새 ZIP 및 다운로드 링크 발급</button><small>내부 사용 전용 · 게시 및 상업적 이용 권한은 부여되지 않습니다.</small></div>}
            <div className="acs-lookbook-export-history"><strong>내부 ZIP 내보내기 이력 ({packageExportHistory.length})</strong>
              {packageExportHistory.length === 0 ? <small>아직 생성된 ZIP 이력이 없습니다.</small> : packageExportHistory.map((entry) => <article key={entry.export_id}>
                <strong>{entry.status === 'available' ? '파일 보관 중' : entry.status === 'expired' ? '보관 기간 만료' : '파일 없음'}</strong>
                <small>{new Date(entry.created_at).toLocaleString()} · {entry.output_count}개 페이지 · {(entry.package_size_bytes / 1024).toFixed(1)} KB</small>
                <small>보관 만료: {new Date(entry.expires_at * 1000).toLocaleString()}</small>
                <small>Export {entry.export_id} · SHA-256 {entry.package_sha256}</small>
                <small>Snapshot SHA-256 {entry.snapshot_sha256}</small>
              </article>)}
              <small>이력은 변경·삭제되지 않는 감사 기록입니다. 파일은 보관 만료 후 정리될 수 있으며, 새 ZIP 생성은 별도의 내보내기 기록을 추가합니다.</small>
            </div>
          </section>}
          {drafts.some((draft) => draft.workflow_status === 'in_review') && <label className="acs-lookbook-review-comment">수정 요청 의견<input value={reviewComment} maxLength={2000} onChange={(event) => setReviewComment(event.currentTarget.value)} placeholder="수정이 필요한 항목을 입력하세요" disabled={busy} /></label>}
          {manifestJson && <pre className="acs-lookbook-manifest">{manifestJson}</pre>}
        </section>
      </div>
    </section>
  );
}

export default LookbookDraftWorkspace;
