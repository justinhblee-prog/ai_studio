import React, { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import ProjectWorkspace from '../ProjectWorkspace';
import AssetWorkspace from '../AssetWorkspace';
import ProductCatalogWorkspace from '../ProductCatalogWorkspace';
import ProjectProductAssignmentWorkspace from '../ProjectProductAssignmentWorkspace';
import PhotoDraftWorkspace from '../PhotoDraftWorkspace';
import LookbookDraftWorkspace from '../LookbookDraftWorkspace';
import GenerationStartWorkspace from '../GenerationStartWorkspace';
import JobResultsWorkspace from '../JobResultsWorkspace';
import LibraryWorkspace from '../LibraryWorkspace';
import { installImageGuard } from './imageGuard.mjs';
import { installUnauthorizedWatcher } from './sessionGuard.mjs';
import SessionExpiredDialog from './SessionExpiredDialog';
import OutputReviewWorkspace from '../OutputReviewWorkspace';
import Studio3DViewer from '../Studio3DViewer';
import { apiRequest, loadOrCreateWorkspace } from './apiClient.mjs';
import { API_BASE_STORAGE_KEY, apiBaseConfigError, resolveApiBase } from './apiBaseUrl.mjs';

// L-13: release builds take the API address only from VITE_API_BASE_URL (no input, no saved override).
// import.meta.env.PROD is replaced at build time, so the input and its strings are removed from release bundles.
const PRODUCTION_BUILD = import.meta.env.PROD;
const API_EDITABLE = !import.meta.env.PROD;
if (!API_EDITABLE) { try { window.localStorage.removeItem(API_BASE_STORAGE_KEY); } catch { /* storage may be disabled */ } }
function rememberApiBase(value: string) {
  if (!API_EDITABLE) return;
  try { window.localStorage.setItem(API_BASE_STORAGE_KEY, value); } catch { /* storage may be disabled */ }
}
import {
  clearSession, getAuthenticatedUser, loadSession, normalizeSupabaseConfig,
  refreshSession, saveSession, sessionFromLocationHash, signInWithPassword,
  signOut, signUpWithPassword,
} from './supabaseAuth.mjs';
import type { AuthSession } from './supabaseAuth.mjs';
import PublicLanding from './PublicLanding';
import LegalGate from './LegalGate';
import AccountPanel from './AccountPanel';
import { gateState, loadLegalStatus } from './legalApi.mjs';
import type { LegalStatus } from './legalApi.mjs';
import './shell.css';

type Workspace = { workspace_id: string; role?: string; owner_id?: string };
type AuthUser = { id: string; email?: string };

const nav = [
  ['overview', '대시보드', '⌂'], ['projects', '프로젝트 관리', '▦'], ['assets', '에셋 라이브러리', '◇'],
  ['viewer', '3D 스튜디오', '◈'], ['products', '상품 카탈로그', '▤'], ['assign', '프로젝트·상품 연결', '⇄'],
  ['photo', '포토 스튜디오', '▧'], ['library', '라이브러리', '▥'], ['generate', '가상 착장 시험 생성', '✦'], ['jobs', '생성 작업 결과', '☰'], ['lookbook', '룩북 스튜디오', '▣'], ['review', '결과물 검수', '✓'],
] as const;

function AuthGate({
  config, apiUrl, onApiUrlChange, onAuthenticated,
}: {
  config: ReturnType<typeof normalizeSupabaseConfig>;
  apiUrl: string;
  onApiUrlChange: (value: string) => void;
  onAuthenticated: (session: AuthSession) => Promise<void>;
}) {
  const [mode, setMode] = useState<'login' | 'signup'>('login');
  const [showAuth, setShowAuth] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setBusy(true); setError(''); setNotice('');
    try {
      if (!config.configured) throw new Error('배포 환경에 VITE_SUPABASE_URL과 VITE_SUPABASE_ANON_KEY가 설정되지 않았습니다.');
      if (mode === 'signup') {
        const result = await signUpWithPassword(config, email, password);
        if (!result.session) {
          setNotice('가입 요청이 접수되었습니다. 이메일 인증을 완료한 뒤 로그인해 주세요.');
          return;
        }
        await onAuthenticated(result.session as AuthSession);
      } else {
        const session = await signInWithPassword(config, email, password);
        await onAuthenticated(session as AuthSession);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '인증 요청에 실패했습니다.');
    } finally { setBusy(false); }
  };

  if (!showAuth) return <PublicLanding onLogin={() => { setMode('login'); setShowAuth(true); }} onSignup={() => { setMode('signup'); setShowAuth(true); }} />;

  return <div className="auth-page">
    <div className="auth-visual"><div className="auth-brand"><span>✦</span><b>AI CREATOR STUDIO</b></div>
      <div className="auth-copy"><small>AI-POWERED CREATIVE PRODUCTION</small><h1>당신의 아이디어를<br/><em>프로페셔널 콘텐츠</em>로.</h1>
        <p>패션·캐릭터·제품 콘텐츠를 기획하고 제작하고 관리하는 통합 크리에이티브 스튜디오.</p></div>
      <div className="auth-visual-footer">DESIGN · CREATE · REVIEW · DELIVER</div>
    </div>
    <div className="auth-panel"><form className="auth-card" onSubmit={submit}>
      <div className="auth-mobile-brand">✦ AI CREATOR STUDIO</div>
      <button type="button" className="auth-back" onClick={() => setShowAuth(false)}>← 홈으로 돌아가기</button>
      <small>YOUR CREATIVE WORKSPACE</small><h2>{mode === 'login' ? '다시 오신 것을 환영합니다.' : '스튜디오 계정 만들기'}</h2>
      <p>{mode === 'login' ? '계정에 로그인하여 작업을 계속하세요.' : '이메일 인증 후 스튜디오를 사용할 수 있습니다.'}</p>
      {API_EDITABLE && <label>Backend API 주소<input type="url" value={apiUrl} onChange={e => onApiUrlChange(e.target.value)} placeholder="https://api.your-domain.com" required disabled={busy}/></label>}
      {apiBaseConfigError({ production: PRODUCTION_BUILD, base: apiUrl }) && <div className="auth-error" role="alert">{apiBaseConfigError({ production: PRODUCTION_BUILD, base: apiUrl })}</div>}
      <label>이메일<input type="email" value={email} onChange={e => setEmail(e.target.value)} autoComplete="email" required disabled={busy}/></label>
      <label>비밀번호<input type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} minLength={8} required disabled={busy}/></label>
      {error && <div className="auth-error" role="alert">{error}</div>}{notice && <div className="auth-notice" role="status">{notice}</div>}
      <button className="auth-submit" type="submit" disabled={busy || !email.trim() || password.length < 8}>{busy ? '처리 중…' : mode === 'login' ? '로그인' : '계정 만들기'} <span>↗</span></button>
      <div className="auth-switch">{mode === 'login' ? '계정이 없으신가요?' : '이미 계정이 있으신가요?'} <button type="button" onClick={() => { setMode(mode === 'login' ? 'signup' : 'login'); setError(''); setNotice(''); }}>{mode === 'login' ? '회원가입' : '로그인'}</button></div>
      <div className="auth-footnote">{API_EDITABLE && <>API 서버: {apiUrl || '미설정'}<br/></>}인증은 Supabase Auth로 처리됩니다. 비밀번호는 이 앱에서 저장하지 않습니다.</div>
    </form></div>
  </div>;
}

function App() {
  const supabaseConfig = useMemo(() => normalizeSupabaseConfig({
    url: import.meta.env.VITE_SUPABASE_URL,
    anonKey: import.meta.env.VITE_SUPABASE_ANON_KEY,
  }), []);
  const [api, setApi] = useState(() => resolveApiBase({
    production: PRODUCTION_BUILD,
    configured: import.meta.env.VITE_API_BASE_URL || '',
    readSaved: () => { try { return window.localStorage.getItem(API_BASE_STORAGE_KEY) || ''; } catch { return ''; } },
    hostname: window.location.hostname,
  }));
  const [session, setSession] = useState<AuthSession | null>(() => loadSession() as AuthSession | null);
  useEffect(() => installImageGuard(document), []); // R-035: no right-click menu / drag-to-save on pictures
  const [user, setUser] = useState<AuthUser | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [workspace, setWorkspace] = useState('');
  const [legal, setLegal] = useState<LegalStatus | null>(null);
  const [job, setJob] = useState('');
  const [page, setPage] = useState('overview');
  const [settings, setSettings] = useState(false);
  const [apiState, setApiState] = useState<'checking' | 'online' | 'offline'>('checking');
  const [connectionError, setConnectionError] = useState('');
  const [busy, setBusy] = useState(false);
  const [expired, setExpired] = useState(false);       // R-030 A: the server no longer accepts the login: ask again on top of the screen
  const [renewedNotice, setRenewedNotice] = useState(false);
  const sessionRef = useRef<AuthSession | null>(null);
  const apiRef = useRef(api);
  const renewing = useRef(false);
  const connectedFor = useRef<string | null>(null); // user id the app is already connected for: a renewed token for the SAME user must not reload the screen
  sessionRef.current = session; apiRef.current = api;

  const connectSession = useCallback(async (candidate: AuthSession) => {
    setBusy(true); setConnectionError(''); setApiState('checking');
    try {
      await apiRequest(api, '/health');
      const [identity, authenticatedUser, legalStatus] = await Promise.all([
        apiRequest(api, '/v1/auth/me', { token: candidate.access_token }),
        getAuthenticatedUser(supabaseConfig, candidate.access_token),
        loadLegalStatus(api, candidate.access_token), // a failed check fails the whole connection: never treated as accepted
      ]);
      if (identity.user_id !== authenticatedUser.id) throw new Error('인증 사용자와 Backend 사용자 식별자가 일치하지 않습니다.');
      setUser(authenticatedUser as AuthUser);
      setLegal(legalStatus as LegalStatus);
      // Workspaces are loaded (or created) only after the legal documents are accepted, so a server that enforces
      // acceptance does not block the connection and nothing is created for a user who has not accepted.
      if (!(legalStatus as LegalStatus).accepted) { setApiState('online'); return; }
      const workspaceResult = await loadOrCreateWorkspace(api, candidate.access_token);
      setWorkspaces(workspaceResult.workspaces as Workspace[]);
      setWorkspace(workspaceResult.workspace.workspace_id);
      setApiState('online');
      connectedFor.current = (authenticatedUser as AuthUser).id;
    } catch (reason) {
      connectedFor.current = null;
      setApiState('offline');
      setConnectionError(reason instanceof Error ? reason.message : 'Backend 연결에 실패했습니다.');
      setSession(candidate); saveSession(candidate);
      throw reason;
    } finally { setBusy(false); }
  }, [api, supabaseConfig]);

  useEffect(() => {
    const linkedSession = sessionFromLocationHash() as AuthSession | null;
    if (linkedSession) {
      saveSession(linkedSession); setSession(linkedSession);
      window.history.replaceState({}, document.title, `${window.location.pathname}${window.location.search}`);
    }
  }, []);

  useEffect(() => { connectedFor.current = null; }, [api, supabaseConfig]); // a different API address always means a fresh connection
  useEffect(() => {
    if (!session) return;
    if (connectedFor.current && connectedFor.current === session.user?.id) return; // same user, new token (renewal or re-login): keep the screen as it is
    connectSession(session).catch(() => undefined);
  }, [session, connectSession]);

  useEffect(() => {
    if (!session) return;
    const delay = Math.max(1000, (session.expires_at - Math.floor(Date.now() / 1000) - 90) * 1000);
    const timer = window.setTimeout(async () => {
      try {
        const next = await refreshSession(supabaseConfig, session);
        saveSession(next); setSession(next);
      } catch {
        setExpired(true); // R-030 A: ask for the password on top of the current screen instead of dropping the screen's contents
      }
    }, delay);
    return () => window.clearTimeout(timer);
  }, [session, supabaseConfig]);

  // R-030 A: a 401 from our API anywhere (any screen) -> try to renew the session quietly; if that fails, ask for the password again.
  useEffect(() => installUnauthorizedWatcher({
    getApiBase: () => apiRef.current,
    onUnauthorized: () => {
      const current = sessionRef.current;
      if (!current || renewing.current) return;
      renewing.current = true;
      refreshSession(supabaseConfig, current)
        .then(next => { saveSession(next); setSession(next); setRenewedNotice(true); })
        .catch(() => setExpired(true))
        .finally(() => { renewing.current = false; });
    },
  }), [supabaseConfig]);

  const renewed = (next: AuthSession) => {
    const previous = sessionRef.current?.user?.id;
    saveSession(next); setSession(next); setExpired(false); setRenewedNotice(true);
    if (previous && next.user?.id && previous !== next.user.id) { // a different account signed in: nothing of the old one may stay
      connectedFor.current = null;
      setUser(null); setWorkspaces([]); setWorkspace(''); setJob(''); setLegal(null); setApiState('checking'); setPage('overview');
    }
  };

  const acceptSession = async (candidate: AuthSession) => {
    saveSession(candidate);
    setSession(candidate);
  };

  const logout = async () => {
    const active = session;
    setBusy(true);
    try { if (active) await signOut(supabaseConfig, active); }
    catch { /* local session is still cleared even if remote revocation is unavailable */ }
    finally {
      connectedFor.current = null;
      clearSession(); setSession(null); setUser(null); setWorkspaces([]); setWorkspace(''); setJob(''); setLegal(null);
      setApiState('checking'); setConnectionError(''); setPage('overview'); setBusy(false); setExpired(false); setRenewedNotice(false);
    }
  };

  const createWorkspace = async () => {
    if (!session) return;
    setBusy(true); setConnectionError('');
    try {
      const created = await apiRequest(api, '/v1/workspaces', {
        token: session.access_token, method: 'POST',
        body: { workspace_id: `ws_${crypto.randomUUID().replace(/-/g, '').slice(0, 24)}` },
      }) as Workspace;
      const next = [...workspaces, created]; setWorkspaces(next); setWorkspace(created.workspace_id);
    } catch (reason) { setConnectionError(reason instanceof Error ? reason.message : 'Workspace 생성에 실패했습니다.'); }
    finally { setBusy(false); }
  };

  if (!session) return <AuthGate config={supabaseConfig} apiUrl={api} onApiUrlChange={value => { setApi(value); rememberApiBase(value); }} onAuthenticated={acceptSession}/>;
  if (gateState(legal) === 'needs-acceptance' && legal && apiState === 'online') return <LegalGate api={api} token={session.access_token} status={legal} onAccepted={next => { setLegal(next); connectSession(session).catch(() => undefined); }} onLogout={logout}/>;
  if (apiState !== 'online' || !workspace) return <div className="connect-page">
    <div className="connect-card"><div className="brandmark">✦</div><small>AUTHENTICATED SESSION</small><h1>스튜디오 연결 확인 중</h1>
      <p>{user?.email || session.user?.email || '로그인 사용자'} 계정 인증은 완료되었습니다. 앱 API와 Workspace를 확인하고 있습니다.</p>
      {connectionError && <div className="auth-error" role="alert">{connectionError}</div>}
      {apiBaseConfigError({ production: PRODUCTION_BUILD, base: api }) && <div className="auth-error" role="alert">{apiBaseConfigError({ production: PRODUCTION_BUILD, base: api })}</div>}
      {API_EDITABLE && <label className="connect-api-label">Backend API 주소<input value={api} onChange={e => { setApi(e.target.value); rememberApiBase(e.target.value); }} placeholder="https://api.your-domain.com"/></label>}
      <div className="connect-meta"><span>Supabase Auth</span><b>세션 보유</b><span>API 상태</span><b>{apiState === 'online' ? '연결됨' : '확인 필요'}</b></div>
      <button className="auth-submit" onClick={() => connectSession(session).catch(() => undefined)} disabled={busy}>{busy ? '연결 확인 중…' : '다시 연결'}</button>
      <button className="text-button" onClick={logout} disabled={busy}>로그아웃</button>
    </div>
  </div>;

  const common = { apiBaseUrl: api, accessToken: session.access_token, workspaceId: workspace };
  const activePage = nav.find(n => n[0] === page)?.[1] || '대시보드';
  return <div className="app">
    <aside className="sidebar"><div className="brand"><div className="brandmark">✦</div><div><b>AI CREATOR STUDIO</b><small>CREATIVE WORKSPACE</small></div></div>
      <div className="workspace-label">WORKSPACE</div>
      {nav.map(([id, label, icon]) => <button key={id} className={`nav ${page === id ? 'active' : ''}`} onClick={() => setPage(id)}><span>{icon}</span>{label}</button>)}
      <div className="side-bottom"><div className="avatar">ACS</div><div><b>{user?.email || 'Studio user'}</b><small>인증된 사용자</small></div><button className="logout-mini" onClick={logout} title="로그아웃">↪</button></div>
    </aside>
    <main className="main"><header className="topbar"><div><span className="crumb">AI CREATOR STUDIO</span><b> / {activePage}</b></div>
      <div className="top-actions"><span className="connection online">API 연결됨</span>
        <select className="workspace-select" aria-label="Workspace 선택" value={workspace} onChange={e => setWorkspace(e.target.value)}>{workspaces.map(w => <option key={w.workspace_id} value={w.workspace_id}>{w.workspace_id}</option>)}</select>
        <button className="outline" onClick={createWorkspace} disabled={busy}>＋ Workspace</button>
        <button className="outline" onClick={() => setSettings(!settings)}>⚙ 설정</button>
      </div></header>
      {settings && <section className="settings"><div className="settings-title"><b>서비스 연결 정보</b><span>인증 토큰은 세션 저장소에 보관하며 화면에 표시하지 않습니다.</span></div>
        {API_EDITABLE && <label>Backend API 주소<input value={api} onChange={e => { setApi(e.target.value); rememberApiBase(e.target.value); }} placeholder="https://api.example.com"/></label>}
        <label>인증 사용자<input value={user?.email || ''} readOnly/></label>
        <label>현재 Workspace<input value={workspace} readOnly/></label>
        <label>결과 검수 Job ID<input value={job} onChange={e => setJob(e.target.value)} placeholder="job UUID"/></label>
        {API_EDITABLE && <p>API 주소를 변경하면 인증된 세션으로 연결 및 사용자 권한을 다시 확인합니다.</p>}
        <AccountPanel api={api} token={session.access_token}/></section>}
      {connectionError && <div className="connection-alert" role="alert">{connectionError}</div>}
      {renewedNotice && !expired && <div className="connection-alert" role="status">다시 로그인되었습니다. 방금 실패한 작업이 있으면 다시 실행해 주세요. <button type="button" className="text-button" onClick={() => setRenewedNotice(false)}>닫기</button></div>}
      {page === 'overview' ? <>
        <section className="hero"><div><div className="eyebrow">AI-POWERED CREATIVE PRODUCTION</div><h1>당신의 아이디어를<br/><em>프로페셔널 콘텐츠</em>로.</h1>
          <p>패션·캐릭터·제품 콘텐츠를 한 공간에서 기획하고 제작하고 관리하세요.</p><button className="primary" onClick={() => setPage('projects')}>프로젝트 시작하기 ↗</button></div>
          <div className="hero-art"><div className="orb orb1"/><div className="orb orb2"/><div className="art-card"><span>CREATIVE<br/>DIRECTION</span><strong>01 — STUDIO</strong></div></div></section>
        <section className="section-head"><div><small>YOUR WORKSPACE</small><h2>크리에이티브 도구</h2></div><span>실제 API 연결 상태: 정상</span></section>
        <div className="tiles">{nav.slice(1).map(([id, label, icon], i) => <button className="tile" key={id} onClick={() => setPage(id)}><span className="tile-icon">{icon}</span><b>{label}</b>
          <small>{['프로젝트 생성 및 상태 관리','파일 업로드·버전·미리보기','3D 모델 업로드 및 뷰어','상품 및 옵션 관리','프로젝트에 상품 연결','이미지 초안 및 작업 실행','룩북 초안·구성·검토','생성 결과 승인 및 반려'][i]}</small><span className="tile-arrow">↗</span></button>)}</div>
        <div className="notice"><b>실제 데이터 기반 작업실</b><span>현재 사용자 인증과 Workspace 권한을 확인했습니다. 각 모듈은 설정된 Backend API를 호출합니다. AI 생성 Provider 및 3D 제작 기능은 별도 실연동 검증 상태를 확인해야 합니다.</span></div>
      </> : <section className="module"><div className="module-head"><div><small>STUDIO MODULE</small><h1>{activePage}</h1><p>인증된 계정 · {workspace}</p></div><button className="outline" onClick={() => setPage('overview')}>← 대시보드</button></div>
        {page === 'projects' && <ProjectWorkspace {...common}/ >}
        {page === 'assets' && <AssetWorkspace {...common}/ >}
        {page === 'viewer' && <Studio3DViewer label="AI Creator Studio 3D Viewer" showGrid autoPlay/>}
        {page === 'products' && <ProductCatalogWorkspace {...common}/ >}
        {page === 'assign' && <ProjectProductAssignmentWorkspace {...common}/ >}
        {page === 'photo' && <PhotoDraftWorkspace {...common}/ >}
        {page === 'library' && <LibraryWorkspace {...common}/>}
        {page === 'jobs' && <JobResultsWorkspace {...common}/>}
        {page === 'generate' && <GenerationStartWorkspace {...common} publicBase={import.meta.env.VITE_ASSET_PUBLIC_BASE_URL || ''}/ >}
        {page === 'lookbook' && <LookbookDraftWorkspace {...common}/ >}
        {page === 'review' && (job.trim() ? <OutputReviewWorkspace apiBaseUrl={api} accessToken={session.access_token} jobId={job.trim()} viewerLabel={(session as { user?: { email?: string; id?: string } }).user?.email || (session as { user?: { id?: string } }).user?.id || ''}/> : <div className="warning">결과 검수를 위해 상단 설정에서 Job ID를 입력해 주세요.</div>)}
      </section>}
    </main>
    {expired && <SessionExpiredDialog config={supabaseConfig} email={user?.email || session.user?.email || ''} onRenewed={renewed} onLogout={logout}/>}
  </div>;
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
