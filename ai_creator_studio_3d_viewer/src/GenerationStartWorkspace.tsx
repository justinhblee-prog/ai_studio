import { ChangeEvent, FormEvent, useCallback, useEffect, useState } from 'react';
import { RIGHTS_CONFIRMATION_COPY, RIGHTS_ERROR_MESSAGES } from './rightsConfirmationCopy';
import { appendRightsDeclaration, rightsErrorCode } from './app/rightsDeclaration.mjs';
import { apiRequest } from './app/apiClient.mjs';
import {
  CATEGORY_OPTIONS, FORMAT_OPTIONS, MODE_OPTIONS, NOT_READY_MESSAGE, RESOLUTION_OPTIONS,
  generationReady, loadGenerationJob, startGeneration,
} from './app/generationStart.mjs';
import type { GenerationJob } from './app/generationStart.mjs';

type ImageAsset = { asset_id: string; original_filename: string };

type Props = { apiBaseUrl: string; accessToken: string; workspaceId: string; publicBase: string };

// R-026: start one virtual try-on job (test generation, mock provider only). Status text only: the mock provider
// produces no image, and results are reviewed in the existing review screen once a real provider exists.
export default function GenerationStartWorkspace({ apiBaseUrl, accessToken, workspaceId, publicBase }: Props) {
  const ready = generationReady(publicBase);
  const [images, setImages] = useState<ImageAsset[]>([]);
  const [modelId, setModelId] = useState('');
  const [garmentId, setGarmentId] = useState('');
  const [category, setCategory] = useState('auto');
  const [mode, setMode] = useState('balanced');
  const [resolution, setResolution] = useState('2k');
  const [outputFormat, setOutputFormat] = useState('png');
  const [prompt, setPrompt] = useState('');
  const [rightsConfirmed, setRightsConfirmed] = useState(false);
  const [depictsPerson, setDepictsPerson] = useState(false);
  const [likenessConsent, setLikenessConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [job, setJob] = useState<GenerationJob | null>(null);
  const [requestKey, setRequestKey] = useState(() => `gen-${crypto.randomUUID()}`);

  const loadImages = useCallback(async () => {
    const result = await apiRequest(apiBaseUrl, `/v1/assets?workspace_id=${encodeURIComponent(workspaceId)}&kind=image`, { token: accessToken });
    setImages(result?.items ?? []);
  }, [apiBaseUrl, accessToken, workspaceId]);

  useEffect(() => {
    setModelId(''); setGarmentId(''); setJob(null); setError('');
    loadImages().catch((reason: unknown) => setError(reason instanceof Error ? reason.message : '이미지 목록을 불러오지 못했습니다.'));
  }, [loadImages]);

  const upload = async (event: ChangeEvent<HTMLInputElement>, assign: (id: string) => void) => {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = '';
    if (!file) return;
    setBusy(true); setError('');
    try {
      const form = new FormData();
      form.set('workspace_id', workspaceId);
      form.set('file', file);
      appendRightsDeclaration(form, { rightsConfirmed, depictsPerson, likenessConsent });
      const response = await fetch(`${apiBaseUrl.replace(/\/+$/, '')}/v1/assets/images`, { method: 'POST', headers: { Authorization: `Bearer ${accessToken}` }, body: form });
      if (!response.ok) {
        const code = await rightsErrorCode(response);
        if (code) throw new Error(RIGHTS_ERROR_MESSAGES[code]);
        const body = await response.json().catch(() => ({}));
        throw new Error(typeof body?.detail === 'string' ? body.detail : body?.detail?.message || `업로드 실패 (${response.status})`);
      }
      const created = await response.json() as ImageAsset;
      await loadImages();
      assign(created.asset_id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '이미지를 업로드하지 못했습니다.');
    } finally { setBusy(false); }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!ready || busy) return;
    setBusy(true); setError(''); setJob(null);
    try {
      const created = await startGeneration({
        api: apiBaseUrl, token: accessToken, publicBase, workspaceId, modelAssetId: modelId, garmentAssetId: garmentId,
        options: { category, mode, resolution, outputFormat, prompt }, idempotencyKey: requestKey,
      });
      setJob(created);
      setRequestKey(`gen-${crypto.randomUUID()}`); // a new click is a new job; a retry of the same failed click reuses the key
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '생성을 시작하지 못했습니다.');
    } finally { setBusy(false); }
  };

  const refresh = async () => {
    if (!job) return;
    setBusy(true); setError('');
    try { setJob(await loadGenerationJob(apiBaseUrl, accessToken, job.job_id)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : '상태를 불러오지 못했습니다.'); }
    finally { setBusy(false); }
  };

  const picker = (label: string, value: string, set: (v: string) => void) => <label>{label}
    <select value={value} onChange={event => set(event.currentTarget.value)} disabled={busy}>
      <option value="">선택</option>
      {images.map(image => <option key={image.asset_id} value={image.asset_id}>{image.original_filename}</option>)}
    </select>
    <input type="file" accept="image/png,image/jpeg,image/webp" aria-label={`${label} 올리기`} disabled={busy} onChange={event => upload(event, set)}/>
  </label>;

  return <section className="module" aria-label="가상 착장 생성 시작">
    <div className="module-head"><div><small>VIRTUAL TRY-ON</small><h1>가상 착장 시험 생성 <span className="tag">시험 생성</span></h1>
      <p>모델 사진과 의류 사진을 골라 생성 작업을 시작합니다. 지금은 <b>시험(mock) 모드</b>이며 실제 AI 이미지는 만들어지지 않습니다.</p></div></div>
    {!ready && <div className="warning" role="status"><b>생성 준비 중</b><span>{NOT_READY_MESSAGE}</span></div>}
    {error && <div className="auth-error" role="alert">{error}</div>}
    <form onSubmit={submit} className="gen-form">
      <fieldset aria-label={RIGHTS_CONFIRMATION_COPY.heading} disabled={busy}>
        <legend>{RIGHTS_CONFIRMATION_COPY.heading} (이미지를 올릴 때 적용)</legend>
        <label><input type="checkbox" checked={rightsConfirmed} onChange={event => setRightsConfirmed(event.currentTarget.checked)}/> {RIGHTS_CONFIRMATION_COPY.rightsConfirmed}</label>
        <label><input type="checkbox" checked={depictsPerson} onChange={event => { setDepictsPerson(event.currentTarget.checked); if (!event.currentTarget.checked) setLikenessConsent(false); }}/> {RIGHTS_CONFIRMATION_COPY.depictsPerson}</label>
        {depictsPerson && <label><input type="checkbox" checked={likenessConsent} onChange={event => setLikenessConsent(event.currentTarget.checked)}/> {RIGHTS_CONFIRMATION_COPY.likenessConsent}</label>}
      </fieldset>
      {picker('모델 사진', modelId, setModelId)}
      {picker('의류 사진', garmentId, setGarmentId)}
      <label>의류 종류<select value={category} onChange={e => setCategory(e.currentTarget.value)} disabled={busy}>{CATEGORY_OPTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
      <label>품질 모드<select value={mode} onChange={e => setMode(e.currentTarget.value)} disabled={busy}>{MODE_OPTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
      <label>해상도<select value={resolution} onChange={e => setResolution(e.currentTarget.value)} disabled={busy}>{RESOLUTION_OPTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
      <label>결과 형식<select value={outputFormat} onChange={e => setOutputFormat(e.currentTarget.value)} disabled={busy}>{FORMAT_OPTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
      <label>추가 요청(선택, 500자 이내)<input value={prompt} maxLength={500} onChange={e => setPrompt(e.currentTarget.value)} disabled={busy}/></label>
      <button type="submit" className="primary" disabled={!ready || busy || !modelId || !garmentId}>{busy ? '처리 중…' : '시험 생성 시작'}</button>
    </form>
    {job && <div className="auth-notice" role="status" aria-label="생성 작업 상태">
      <div>작업 ID: <code>{job.job_id}</code></div>
      <div>상태: <b>{job.status}</b> · 엔진: {job.provider}{job.provider === 'mock' ? ' (시험)' : ''}</div>
      {job.provider !== 'mock' && <div role="alert">시험 모드가 아닌 엔진으로 접수되었습니다. 운영자에게 알려 주세요.</div>}
      {job.message && <div>{job.message}</div>}
      <button type="button" className="outline" onClick={refresh} disabled={busy}>상태 새로고침</button>
    </div>}
    <p className="gen-note">시작한 작업의 상태와 결과는 "생성 작업 결과" 메뉴에서 확인합니다(시험 엔진은 이미지를 만들지 않습니다).</p>
  </section>;
}
