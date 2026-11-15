import { FormEvent, useEffect, useRef, useState } from 'react';
import { signInWithPassword } from './supabaseAuth.mjs';
import type { AuthSession } from './supabaseAuth.mjs';

type Props = {
  config: Parameters<typeof signInWithPassword>[0];
  email: string;
  onRenewed: (session: AuthSession) => void;
  onLogout: () => void;
};

// R-030 A: shown ON TOP of the current screen when the server stops accepting the login. The screen underneath stays mounted, so
// whatever was typed there is kept; after signing in again the person continues where they were.
export default function SessionExpiredDialog({ config, email, onRenewed, onLogout }: Props) {
  const [mail, setMail] = useState(email);
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const passwordRef = useRef<HTMLInputElement>(null);
  useEffect(() => { passwordRef.current?.focus(); }, []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true); setError('');
    try { onRenewed(await signInWithPassword(config, mail, password) as AuthSession); }
    catch (reason) { setError(reason instanceof Error ? reason.message : '로그인하지 못했습니다. 이메일과 비밀번호를 확인해 주세요.'); }
    finally { setBusy(false); }
  };

  return <div className="session-expired-backdrop" style={{ position: 'fixed', inset: 0, background: '#0008', display: 'grid', placeItems: 'center', zIndex: 50, padding: 16 }}>
    <form className="auth-card" role="dialog" aria-modal="true" aria-labelledby="session-expired-title" onSubmit={submit} style={{ width: 'min(100%, 420px)' }}>
      <h2 id="session-expired-title">로그인이 만료되었습니다</h2>
      <p>보안을 위해 다시 로그인해야 합니다. <b>지금 화면에 작성 중이던 내용은 그대로 유지됩니다.</b> 로그인하면 이어서 작업할 수 있습니다.</p>
      <label>이메일<input type="email" value={mail} onChange={e => setMail(e.target.value)} autoComplete="email" required disabled={busy}/></label>
      <label>비밀번호<input ref={passwordRef} type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" minLength={8} required disabled={busy}/></label>
      {error && <div className="auth-error" role="alert">{error}</div>}
      <button className="auth-submit" type="submit" disabled={busy || !mail.trim() || password.length < 8}>{busy ? '확인 중…' : '다시 로그인'}</button>
      <button type="button" className="text-button" onClick={onLogout} disabled={busy}>로그아웃하고 처음 화면으로</button>
    </form>
  </div>;
}
