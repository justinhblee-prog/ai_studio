import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import './ProjectWorkspace.css';
import { useRequestScope } from './useRequestScope';
import { publishProjectLifecycleChange } from './projectLifecycleEvents.mjs';
import { errorText, responseErrorText } from './app/errorMessages.mjs';

type ProjectStatus = 'ACTIVE' | 'ARCHIVED' | 'COMPLETED';
type Project = {
  project_id: string;
  workspace_id: string;
  name: string;
  project_type: string;
  status: ProjectStatus;
  description: string | null;
  external_reference: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
};

export type ProjectWorkspaceProps = {
  apiBaseUrl: string;
  accessToken: string;
  workspaceId: string;
};

async function responseError(response: Response): Promise<string> {
  return responseErrorText(response);
}

export function ProjectWorkspace({ apiBaseUrl, accessToken, workspaceId }: ProjectWorkspaceProps) {
  const base = apiBaseUrl.replace(/\/$/, '');
  const headers = { Authorization: `Bearer ${accessToken}` };
  const { capture: captureScope, isCurrent: isScopeCurrent } = useRequestScope([base, accessToken, workspaceId]);
  const [projects, setProjects] = useState<Project[]>([]);
  const loadSequenceRef = useRef(0);
  const requestScopeRef = useRef({ workspaceId, accessToken });
  requestScopeRef.current = { workspaceId, accessToken };
  const [name, setName] = useState('');
  const [projectType, setProjectType] = useState('campaign');
  const [description, setDescription] = useState('');
  const [externalReference, setExternalReference] = useState('');
  const [status, setStatus] = useState<ProjectStatus>('ACTIVE');
  const [editingProjectId, setEditingProjectId] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    const requestId = ++loadSequenceRef.current;
    const response = await fetch(`${base}/v1/projects?workspace_id=${encodeURIComponent(workspaceId)}`, { headers, signal });
    if (!response.ok) throw new Error(await responseError(response));
    const result = await response.json() as { items: Project[] };
    if (requestId !== loadSequenceRef.current || requestScopeRef.current.workspaceId !== workspaceId || requestScopeRef.current.accessToken !== accessToken) return;
    setProjects(result.items);
  }, [base, accessToken, workspaceId]);

  useEffect(() => {
    setProjects([]); setName(''); setProjectType('campaign'); setDescription(''); setExternalReference('');
    setStatus('ACTIVE'); setEditingProjectId(''); setError(null); setBusy(false);
  }, [base, accessToken, workspaceId]);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(errorText(reason, '프로젝트를 불러오지 못했습니다.'));
    });
    return () => controller.abort();
  }, [load]);

  const clearForm = useCallback(() => {
    setEditingProjectId(''); setName(''); setProjectType('campaign'); setDescription('');
    setExternalReference(''); setStatus('ACTIVE');
  }, []);

  const startEdit = useCallback((project: Project) => {
    setEditingProjectId(project.project_id);
    setName(project.name);
    setProjectType(project.project_type);
    setDescription(project.description || '');
    setExternalReference(project.external_reference || '');
    setStatus(project.status);
  }, []);

  const save = useCallback(async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const scope = captureScope();
    setBusy(true); setError(null);
    try {
      const headersWithJson = { ...headers, 'Content-Type': 'application/json' };
      const response = editingProjectId
        ? await fetch(`${base}/v1/projects/${encodeURIComponent(editingProjectId)}`, {
            method: 'PUT', headers: headersWithJson,
            body: JSON.stringify({ name: name.trim(), project_type: projectType.trim(), status, description: description.trim() || null }),
          })
        : await fetch(`${base}/v1/projects`, {
            method: 'POST', headers: headersWithJson,
            body: JSON.stringify({ workspace_id: workspaceId, name: name.trim(), project_type: projectType.trim(), description: description.trim() || null, external_reference: externalReference.trim() || null }),
          });
      if (!response.ok) throw new Error(await responseError(response));
      if (!isScopeCurrent(scope)) return;
      if (editingProjectId) publishProjectLifecycleChange({ workspaceId, projectId: editingProjectId });
      clearForm();
      await load();
    } catch (reason) {
      if (isScopeCurrent(scope)) setError(errorText(reason, '프로젝트를 저장하지 못했습니다.'));
    } finally {
      if (isScopeCurrent(scope)) setBusy(false);
    }
  }, [base, accessToken, workspaceId, editingProjectId, name, projectType, status, description, externalReference, clearForm, load, captureScope, isScopeCurrent]);

  const statusAction = useCallback(async (project: Project, nextStatus: ProjectStatus) => {
    const scope = captureScope();
    setBusy(true); setError(null);
    try {
      const response = await fetch(`${base}/v1/projects/${encodeURIComponent(project.project_id)}`, {
        method: 'PUT', headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: project.name, project_type: project.project_type, status: nextStatus, description: project.description }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      if (!isScopeCurrent(scope)) return;
      if (editingProjectId === project.project_id) setStatus(nextStatus);
      publishProjectLifecycleChange({ workspaceId, projectId: project.project_id });
      await load();
    } catch (reason) {
      if (isScopeCurrent(scope)) setError(errorText(reason, '프로젝트 상태를 변경하지 못했습니다.'));
    } finally {
      if (isScopeCurrent(scope)) setBusy(false);
    }
  }, [base, accessToken, workspaceId, editingProjectId, load, captureScope, isScopeCurrent]);

  return (
    <section className="acs-project-workspace" aria-label="프로젝트 관리">
      <header><div><strong>프로젝트 관리</strong><span>캠페인 및 작업 단위 관리</span></div><span>{projects.length}개</span></header>
      <p className="acs-project-workspace-notice">프로젝트 보관/완료는 기록을 유지하는 상태 변경입니다. 활성 Lookbook 초안에서 사용 중인 프로젝트는 초안을 먼저 보관해야 상태를 변경할 수 있습니다. 외부 참조는 생성 시 등록하며 이후에는 읽기 전용입니다.</p>
      {error && <p className="acs-project-workspace-error" role="alert">{error}</p>}
      <div className="acs-project-workspace-grid">
        <form onSubmit={save}>
          <strong>{editingProjectId ? '프로젝트 편집' : '새 프로젝트'}</strong>
          <label>프로젝트명<input value={name} maxLength={120} onChange={(event) => setName(event.currentTarget.value)} disabled={busy} required /></label>
          <label>유형<input value={projectType} maxLength={64} onChange={(event) => setProjectType(event.currentTarget.value)} disabled={busy} required /></label>
          <label>설명<textarea value={description} maxLength={2000} onChange={(event) => setDescription(event.currentTarget.value)} disabled={busy} rows={3} /></label>
          {editingProjectId ? <label>상태<select value={status} onChange={(event) => setStatus(event.currentTarget.value as ProjectStatus)} disabled={busy}>
            <option value="ACTIVE">활성</option><option value="COMPLETED">완료</option><option value="ARCHIVED">보관</option>
          </select></label> : <label>외부 참조<input value={externalReference} maxLength={128} onChange={(event) => setExternalReference(event.currentTarget.value)} disabled={busy} placeholder="선택 사항" /></label>}
          <button type="submit" disabled={busy || !name.trim() || !projectType.trim()}>{editingProjectId ? '변경 저장' : '프로젝트 생성'}</button>
          {editingProjectId && <button type="button" disabled={busy} onClick={clearForm}>편집 취소</button>}
        </form>
        <section className="acs-project-workspace-list" aria-label="프로젝트 목록">
          {projects.map((project) => <article key={project.project_id}>
            <div><strong>{project.name}</strong><span>{project.project_type} · {project.status}</span>{project.description && <p>{project.description}</p>}{project.external_reference && <small>외부 참조: {project.external_reference}</small>}</div>
            <div className="acs-project-workspace-actions">
              <button type="button" disabled={busy} onClick={() => startEdit(project)}>편집</button>
              {project.status === 'ACTIVE' && <><button type="button" disabled={busy} onClick={() => statusAction(project, 'COMPLETED')}>완료</button><button type="button" disabled={busy} onClick={() => statusAction(project, 'ARCHIVED')}>보관</button></>}
              {project.status !== 'ACTIVE' && <button type="button" disabled={busy} onClick={() => statusAction(project, 'ACTIVE')}>다시 활성화</button>}
            </div>
          </article>)}
          {projects.length === 0 && <p>등록된 프로젝트가 없습니다.</p>}
        </section>
      </div>
    </section>
  );
}

export default ProjectWorkspace;
