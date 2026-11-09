import { useCallback, useEffect, useRef, useState } from 'react';
import './ProjectProductAssignmentWorkspace.css';
import { useRequestScope } from './useRequestScope';
import { subscribeProjectLifecycleChanges } from './projectLifecycleEvents.mjs';

type Project = { project_id: string; workspace_id: string; name: string; project_type: string; status: string; description: string | null; external_reference: string | null; created_by: string; created_at: string; updated_at: string };
type Product = { product_id: string; workspace_id: string; sku: string; name: string; description: string | null; category: string; status: string; created_by: string; created_at: string; updated_at: string; archived_at?: string | null; image_asset_ids: string[]; variants: Array<{ variant_id: string; product_id: string; workspace_id: string; sku: string; option_values: Record<string, string>; image_asset_ids: string[]; status: string; created_by: string; created_at: string; updated_at: string; archived_at?: string | null }> };
type AssignmentEvent = { event_id: string; event_type: string; details: { added?: string[]; removed?: string[]; reordered?: boolean }; created_at: string };

export type ProjectProductAssignmentWorkspaceProps = {
  apiBaseUrl: string;
  accessToken: string;
  workspaceId: string;
};

async function responseError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    const detail = body?.detail;
    return typeof detail === 'string' ? detail : detail?.message || `요청 실패 (${response.status})`;
  } catch { return `요청 실패 (${response.status})`; }
}

export function ProjectProductAssignmentWorkspace({ apiBaseUrl, accessToken, workspaceId }: ProjectProductAssignmentWorkspaceProps) {
  const base = apiBaseUrl.replace(/\/$/, '');
  const headers = { Authorization: `Bearer ${accessToken}` };
  const { capture: captureScope, isCurrent: isScopeCurrent } = useRequestScope([base, accessToken, workspaceId]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [projectId, setProjectId] = useState('');
  const [productIds, setProductIds] = useState<string[]>([]);
  const [events, setEvents] = useState<AssignmentEvent[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const catalogLoadSequenceRef = useRef(0);
  const assignmentLoadSequenceRef = useRef(0);
  const selectedProjectRef = useRef(projectId);
  selectedProjectRef.current = projectId;

  const loadCatalog = useCallback(async (signal?: AbortSignal) => {
    const scope = captureScope();
    const requestId = ++catalogLoadSequenceRef.current;
    const [projectResponse, productResponse] = await Promise.all([
      fetch(`${base}/v1/projects?workspace_id=${encodeURIComponent(workspaceId)}&status=ACTIVE`, { headers, signal }),
      fetch(`${base}/v1/products?workspace_id=${encodeURIComponent(workspaceId)}&limit=100`, { headers, signal }),
    ]);
    if (signal?.aborted || !isScopeCurrent(scope) || requestId !== catalogLoadSequenceRef.current) return;
    if (!projectResponse.ok) throw new Error(await responseError(projectResponse));
    if (!productResponse.ok) throw new Error(await responseError(productResponse));
    const projectResult = await projectResponse.json() as { items: Project[] };
    const productResult = await productResponse.json() as { items: Product[] };
    if (signal?.aborted || !isScopeCurrent(scope) || requestId !== catalogLoadSequenceRef.current) return;
    setProjects(projectResult.items); setProducts(productResult.items);
    const nextProjectId = projectResult.items.some((item) => item.project_id === selectedProjectRef.current)
      ? selectedProjectRef.current
      : projectResult.items[0]?.project_id || '';
    if (nextProjectId !== selectedProjectRef.current) {
      assignmentLoadSequenceRef.current += 1;
      setProductIds([]);
      setEvents([]);
    }
    setProjectId(nextProjectId);
  }, [base, accessToken, workspaceId, captureScope, isScopeCurrent]);

  const loadAssignments = useCallback(async (selectedProjectId: string, signal?: AbortSignal) => {
    const scope = captureScope();
    const requestId = ++assignmentLoadSequenceRef.current;
    if (!selectedProjectId) { if (!signal?.aborted && isScopeCurrent(scope) && requestId === assignmentLoadSequenceRef.current && !selectedProjectRef.current) { setProductIds([]); setEvents([]); } return; }
    const [assignmentResponse, eventResponse] = await Promise.all([
      fetch(`${base}/v1/projects/${encodeURIComponent(selectedProjectId)}/products`, { headers, signal }),
      fetch(`${base}/v1/projects/${encodeURIComponent(selectedProjectId)}/product-events`, { headers, signal }),
    ]);
    if (!assignmentResponse.ok) throw new Error(await responseError(assignmentResponse));
    if (!eventResponse.ok) throw new Error(await responseError(eventResponse));
    const assignmentResult = await assignmentResponse.json() as { items: Product[] };
    const eventResult = await eventResponse.json() as { items: AssignmentEvent[] };
    if (signal?.aborted || !isScopeCurrent(scope) || requestId !== assignmentLoadSequenceRef.current || selectedProjectRef.current !== selectedProjectId) return;
    setProductIds(assignmentResult.items.map((item) => item.product_id)); setEvents(eventResult.items);
  }, [base, accessToken, captureScope, isScopeCurrent]);

  useEffect(() => {
    setProjects([]); setProducts([]); setProjectId(''); setProductIds([]); setEvents([]); setError(null); setBusy(false);
  }, [base, accessToken, workspaceId]);

  useEffect(() => {
    const controller = new AbortController();
    loadCatalog(controller.signal).catch((reason: unknown) => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : '프로젝트/상품을 불러오지 못했습니다.'); });
    return () => controller.abort();
  }, [loadCatalog]);

  useEffect(() => subscribeProjectLifecycleChanges((change) => {
    if (change.workspaceId !== workspaceId) return;
    loadCatalog().catch((reason: unknown) => setError(reason instanceof Error ? reason.message : '프로젝트 상태 변경을 반영하지 못했습니다.'));
  }), [workspaceId, loadCatalog]);

  useEffect(() => {
    // Never display the previous project's assignments/history while the new
    // project's two reads are in flight. Invalidate any prior hydration first.
    assignmentLoadSequenceRef.current += 1;
    setProductIds([]);
    setEvents([]);
    setError(null);
    const controller = new AbortController();
    loadAssignments(projectId, controller.signal).catch((reason: unknown) => {
      if (!controller.signal.aborted && selectedProjectRef.current === projectId) {
        setError(reason instanceof Error ? reason.message : '상품 연결을 불러오지 못했습니다.');
      }
    });
    return () => {
      controller.abort();
      assignmentLoadSequenceRef.current += 1;
    };
  }, [projectId, loadAssignments]);

  const selectProject = useCallback((nextProjectId: string) => {
    if (nextProjectId === selectedProjectRef.current) return;
    assignmentLoadSequenceRef.current += 1;
    setProductIds([]);
    setEvents([]);
    setError(null);
    setProjectId(nextProjectId);
  }, []);

  const save = useCallback(async () => {
    if (!projectId) return;
    const scope = captureScope();
    const selectedProjectId = projectId;
    setBusy(true); setError(null);
    try {
      const response = await fetch(`${base}/v1/projects/${encodeURIComponent(projectId)}/products`, {
        method: 'PUT', headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_ids: productIds }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      if (!isScopeCurrent(scope)) return;
      await loadAssignments(selectedProjectId);
    } catch (reason) { if (isScopeCurrent(scope)) setError(reason instanceof Error ? reason.message : '상품 연결을 저장하지 못했습니다.'); }
    finally { if (isScopeCurrent(scope)) setBusy(false); }
  }, [base, accessToken, workspaceId, projectId, productIds, loadAssignments, captureScope, isScopeCurrent]);

  return (
    <section className="acs-project-products" aria-label="프로젝트 상품 연결">
      <header><div><strong>프로젝트 상품 연결</strong><span>캠페인별 상품 구성 및 순서 관리</span></div></header>
      <p className="acs-project-products-notice">프로젝트에 연결된 상품은 해당 프로젝트가 활성 상태인 동안 보관할 수 없습니다. 연결 변경 이력은 유지됩니다.</p>
      {error && <p className="acs-project-products-error" role="alert">{error}</p>}
      <div className="acs-project-products-grid">
        <label>프로젝트<select value={projectId} onChange={(event) => selectProject(event.currentTarget.value)} disabled={busy || projects.length === 0}>
          {projects.map((item) => <option key={item.project_id} value={item.project_id}>{item.name}</option>)}
        </select></label>
        <label>연결할 상품 (선택 순서가 프로젝트 표시 순서입니다)<select multiple size={7} value={productIds} onChange={(event) => setProductIds(Array.from(event.currentTarget.selectedOptions, (option) => option.value))} disabled={busy || products.length === 0}>
          {products.map((item) => <option key={item.product_id} value={item.product_id}>{item.sku} · {item.name}</option>)}
        </select></label>
        <button type="button" onClick={save} disabled={busy || !projectId}>프로젝트 상품 구성 저장</button>
      </div>
      <section className="acs-project-products-history" aria-label="상품 연결 변경 이력">
        <strong>변경 이력 · {events.length}건</strong>
        {events.slice(0, 8).map((event) => <p key={event.event_id}>{new Date(event.created_at).toLocaleString()} · 추가 {event.details.added?.length || 0} · 제거 {event.details.removed?.length || 0}{event.details.reordered ? ' · 순서 변경' : ''}</p>)}
        {events.length === 0 && <p>아직 변경 이력이 없습니다.</p>}
      </section>
    </section>
  );
}

export default ProjectProductAssignmentWorkspace;
