import { ChangeEvent, useCallback, useEffect, useRef, useState } from 'react';
import Studio3DViewer from './Studio3DViewer';
import './AssetWorkspace.css';
import { useRequestScope } from './useRequestScope';

type AssetRecord = {
  asset_id: string;
  owner_id: string;
  workspace_id: string;
  original_filename: string;
  media_type: string;
  size_bytes: number;
  checksum_sha256: string;
  gltf_version: string | null;
  embedded_binary: boolean;
  asset_kind: 'model' | 'image';
  created_at: string;
};

type AssetVersionRecord = {
  version_id: string;
  asset_id: string;
  workspace_id: string;
  version_number: number;
  media_type: string;
  size_bytes: number;
  checksum_sha256: string;
  created_by: string;
  created_at: string;
  is_current: boolean;
};

type AssetWorkspaceProps = {
  /** API origin, e.g. https://studio.example.com. */
  apiBaseUrl: string;
  /** Short-lived application access token; never persist it in local storage. */
  accessToken: string;
  /** Owner-scoped workspace namespace. */
  workspaceId: string;
};

async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    const detail = body?.detail;
    return typeof detail === 'string' ? detail : detail?.message || `요청 실패 (${response.status})`;
  } catch {
    return `요청 실패 (${response.status})`;
  }
}

export function AssetWorkspace({ apiBaseUrl, accessToken, workspaceId }: AssetWorkspaceProps) {
  const [assets, setAssets] = useState<AssetRecord[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [versions, setVersions] = useState<AssetVersionRecord[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const selectionRequestRef = useRef(0);
  const selectionControllerRef = useRef<AbortController | null>(null);

  const base = apiBaseUrl.replace(/\/$/, '');
  const headers = { Authorization: `Bearer ${accessToken}` };
  const { capture: captureScope, isCurrent: isScopeCurrent } = useRequestScope([base, accessToken, workspaceId]);

  const loadAssets = useCallback(async (signal?: AbortSignal) => {
    const scope = captureScope();
    const response = await fetch(`${base}/v1/assets?workspace_id=${encodeURIComponent(workspaceId)}&kind=model`, { headers, signal });
    if (!response.ok) throw new Error(await readError(response));
    const result = await response.json() as { items: AssetRecord[] };
    if (signal?.aborted || !isScopeCurrent(scope)) return;
    setAssets(result.items);
    setSelectedId((current) => current && result.items.some((item) => item.asset_id === current) ? current : null);
  }, [base, accessToken, workspaceId, captureScope, isScopeCurrent]);

  useEffect(() => {
    selectionRequestRef.current += 1;
    selectionControllerRef.current?.abort();
    selectionControllerRef.current = null;
    setAssets([]);
    setSelectedId(null);
    setPreviewUrl(null);
    setVersions([]);
    setError(null);
    setBusy(false);
    const controller = new AbortController();
    loadAssets(controller.signal).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : '자산 목록을 불러오지 못했습니다.');
    });
    return () => {
      controller.abort();
      selectionRequestRef.current += 1;
      selectionControllerRef.current?.abort();
      selectionControllerRef.current = null;
    };
  }, [loadAssets]);

  const loadVersions = useCallback(async (assetId: string, signal?: AbortSignal) => {
    const response = await fetch(`${base}/v1/assets/${encodeURIComponent(assetId)}/versions`, { headers, signal });
    if (!response.ok) throw new Error(await readError(response));
    const result = await response.json() as { items: AssetVersionRecord[] };
    return result.items;
  }, [base, accessToken]);

  const selectAsset = useCallback(async (assetId: string) => {
    selectionControllerRef.current?.abort();
    const controller = new AbortController();
    selectionControllerRef.current = controller;
    const scope = captureScope();
    const requestId = ++selectionRequestRef.current;
    const isSelectionCurrent = () => requestId === selectionRequestRef.current && isScopeCurrent(scope) && !controller.signal.aborted;
    setBusy(true);
    setError(null);
    setPreviewUrl(null);
    setVersions([]);
    setSelectedId(assetId);
    try {
      const nextVersions = await loadVersions(assetId, controller.signal);
      if (!isSelectionCurrent()) return;
      const currentVersion = nextVersions.find((version) => version.is_current);
      if (!currentVersion) throw new Error('현재 AssetVersion을 찾을 수 없습니다.');
      setVersions(nextVersions);
      // Authenticated content endpoint rechecks workspace membership for every
      // request; the viewer supplies the short-lived in-memory Bearer token.
      setPreviewUrl(`${base}/v1/assets/${encodeURIComponent(assetId)}/versions/${encodeURIComponent(currentVersion.version_id)}/preview-content`);
    } catch (reason) {
      if (isSelectionCurrent()) {
        setError(reason instanceof Error ? reason.message : '미리보기 주소를 발급하지 못했습니다.');
        setSelectedId(null);
      }
    } finally {
      if (isSelectionCurrent()) setBusy(false);
      if (selectionControllerRef.current === controller) selectionControllerRef.current = null;
    }
  }, [base, accessToken, loadVersions, captureScope, isScopeCurrent]);

  const restoreVersion = useCallback(async (assetId: string, versionId: string) => {
    const scope = captureScope();
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${base}/v1/assets/${encodeURIComponent(assetId)}/versions/${encodeURIComponent(versionId)}/restore`, {
        method: 'POST', headers,
      });
      if (!response.ok) throw new Error(await readError(response));
      if (!isScopeCurrent(scope)) return;
      // The restored version changes the current immutable version pointer.
      // Drop the prior signed preview and history before hydrating the new one.
      selectionRequestRef.current += 1;
      selectionControllerRef.current?.abort();
      selectionControllerRef.current = null;
      setPreviewUrl(null);
      setVersions([]);
      await loadAssets();
      if (!isScopeCurrent(scope)) return;
      await selectAsset(assetId);
    } catch (reason) {
      if (isScopeCurrent(scope)) setError(reason instanceof Error ? reason.message : '이전 버전을 복원하지 못했습니다.');
    } finally {
      if (isScopeCurrent(scope)) setBusy(false);
    }
  }, [base, accessToken, loadAssets, selectAsset, captureScope, isScopeCurrent]);

  const upload = useCallback(async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = '';
    if (!file) return;
    const scope = captureScope();
    setBusy(true);
    setError(null);
    setPreviewUrl(null);
    try {
      const form = new FormData();
      form.set('workspace_id', workspaceId);
      form.set('file', file);
      const response = await fetch(`${base}/v1/assets`, { method: 'POST', headers, body: form });
      if (!response.ok) throw new Error(await readError(response));
      const created = await response.json() as AssetRecord;
      if (!isScopeCurrent(scope)) return;
      await loadAssets();
      if (!isScopeCurrent(scope)) return;
      await selectAsset(created.asset_id);
    } catch (reason) {
      if (isScopeCurrent(scope)) setError(reason instanceof Error ? reason.message : '파일을 업로드하지 못했습니다.');
    } finally {
      if (isScopeCurrent(scope)) setBusy(false);
    }
  }, [base, accessToken, workspaceId, loadAssets, selectAsset, captureScope, isScopeCurrent]);

  const removeAsset = useCallback(async (assetId: string) => {
    const scope = captureScope();
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${base}/v1/assets/${encodeURIComponent(assetId)}`, { method: 'DELETE', headers });
      if (!response.ok) throw new Error(await readError(response));
      if (!isScopeCurrent(scope)) return;
      if (selectedId === assetId) {
        selectionRequestRef.current += 1;
        selectionControllerRef.current?.abort();
        selectionControllerRef.current = null;
        setSelectedId(null);
        setPreviewUrl(null);
        setVersions([]);
      }
      await loadAssets();
    } catch (reason) {
      if (isScopeCurrent(scope)) setError(reason instanceof Error ? reason.message : '자산을 삭제하지 못했습니다.');
    } finally {
      if (isScopeCurrent(scope)) setBusy(false);
    }
  }, [base, accessToken, selectedId, loadAssets, captureScope, isScopeCurrent]);

  const selected = assets.find((asset) => asset.asset_id === selectedId) ?? null;

  return (
    <section className="acs-asset-workspace" aria-label="3D 자산 작업실">
      <aside className="acs-asset-sidebar">
        <header className="acs-asset-header">
          <div><strong>3D 자산</strong><span>GLB / GLTF</span></div>
          <label className={`acs-asset-upload${busy ? ' is-disabled' : ''}`}>
            모델 추가
            <input type="file" accept=".glb,.gltf,model/gltf-binary,model/gltf+json" disabled={busy} onChange={upload} />
          </label>
        </header>
        {error && <p className="acs-asset-error" role="alert">{error}</p>}
        <ul className="acs-asset-list">
          {assets.map((asset) => (
            <li key={asset.asset_id} className={asset.asset_id === selectedId ? 'is-selected' : ''}>
              <button type="button" className="acs-asset-select" disabled={busy} onClick={() => selectAsset(asset.asset_id)}>
                <strong>{asset.original_filename}</strong>
                <span>{(asset.size_bytes / (1024 * 1024)).toFixed(2)} MB · glTF {asset.gltf_version}</span>
              </button>
              <button type="button" className="acs-asset-delete" aria-label={`${asset.original_filename} 삭제`} disabled={busy} onClick={() => removeAsset(asset.asset_id)}>삭제</button>
            </li>
          ))}
          {assets.length === 0 && <li className="acs-asset-empty">등록된 3D 모델이 없습니다.</li>}
        </ul>
      </aside>
      <main className="acs-asset-preview">
        {busy && <div className="acs-asset-busy" role="status">처리 중…</div>}
        {selected && <div className="acs-asset-preview-title"><strong>{selected.original_filename}</strong><span>{selected.checksum_sha256.slice(0, 12)}…</span></div>}
        <Studio3DViewer modelUrl={previewUrl} accessToken={accessToken} label="3D 자산 미리보기" />
        {selected && <section className="acs-asset-versions" aria-label="버전 이력">
          <header><strong>버전 이력</strong><span>{versions.length}개</span></header>
          {versions.map((version) => (
            <div className="acs-asset-version" key={version.version_id}>
              <div><strong>v{version.version_number}{version.is_current ? ' · 현재' : ''}</strong>
                <span>{new Date(version.created_at).toLocaleString()} · {(version.size_bytes / 1024).toFixed(1)} KB</span></div>
              {!version.is_current && <button type="button" disabled={busy} onClick={() => restoreVersion(selected.asset_id, version.version_id)}>이 버전으로 복원</button>}
            </div>
          ))}
          {versions.length === 0 && <p>버전 이력이 없습니다.</p>}
        </section>}
      </main>
    </section>
  );
}

export default AssetWorkspace;
