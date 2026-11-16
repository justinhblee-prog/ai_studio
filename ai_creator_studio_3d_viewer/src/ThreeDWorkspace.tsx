import { ChangeEvent, useCallback, useEffect, useState } from 'react';
import Studio3DViewer from './Studio3DViewer';
import { errorText } from './app/errorMessages.mjs';
import { loadFeatures } from './app/characterClient.mjs';
import { BACKGROUNDS, currentVersionId, listModels, listVersions, modelContentUrl, uploadModel, validateModelFile } from './app/threeDClient.mjs';

type Props = { apiBaseUrl: string; accessToken: string; workspaceId: string };
type Model = { asset_id: string; original_filename: string };

// R-038: 3D Studio, viewing part. The member uploads a .glb/.gltf, turns and zooms it in the viewer and picks a stage background.
export default function ThreeDWorkspace({ apiBaseUrl, accessToken, workspaceId }: Props) {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [models, setModels] = useState<Model[] | null>(null);
  const [selected, setSelected] = useState('');
  const [modelUrl, setModelUrl] = useState<string | null>(null);
  const [background, setBackground] = useState(BACKGROUNDS[0].value);
  const [error, setError] = useState('');
  const [viewerError, setViewerError] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError('');
    try {
      const [features, list] = await Promise.all([loadFeatures(apiBaseUrl, accessToken), listModels(apiBaseUrl, accessToken, workspaceId)]);
      setEnabled(Boolean(features?.features?.three_d?.enabled)); setModels(list?.items ?? []);
    } catch (reason) { setError(errorText(reason, '3D 모델을 불러오지 못했습니다.')); setModels([]); }
  }, [apiBaseUrl, accessToken, workspaceId]);
  useEffect(() => { setModels(null); setSelected(''); setModelUrl(null); load(); }, [load]);

  const choose = async (assetId: string) => {
    setSelected(assetId); setViewerError(''); setModelUrl(null);
    if (!assetId) return;
    try {
      const version = currentVersionId(await listVersions(apiBaseUrl, accessToken, assetId));
      if (!version) throw new Error('모델의 현재 버전을 찾지 못했습니다.');
      setModelUrl(modelContentUrl(apiBaseUrl, assetId, version));
    } catch (reason) { setError(errorText(reason, '모델을 열지 못했습니다.')); }
  };

  const upload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = '';
    const problem = validateModelFile(file);
    if (problem) { setError(problem); return; }
    setBusy(true); setError('');
    try { const created = await uploadModel(apiBaseUrl, accessToken, workspaceId, file as File); await load(); await choose(created.asset_id); }
    catch (reason) { setError(errorText(reason, '모델을 올리지 못했습니다.')); } finally { setBusy(false); }
  };

  return <section className="module" aria-label="3D 스튜디오">
    <div className="module-head"><div><small>3D STUDIO</small><h1>3D 스튜디오</h1>
      <p>.glb 또는 .gltf 파일을 올려 돌려 보고 확대해 볼 수 있습니다. 외부 AI 서비스로 전송되지 않으며 작업공간 안에서만 보입니다.</p></div></div>
    {enabled === false && <div className="warning" role="status"><b>파일럿 시험판</b><span>3D 스튜디오는 아직 시험판입니다. 관리자가 켜면 모델을 올릴 수 있습니다. 이미 올린 모델은 볼 수 있습니다.</span></div>}
    {error && <div className="auth-error" role="alert">{error} <button type="button" className="outline" onClick={load}>다시 시도</button></div>}
    <div className="gen-form">
      <label>모델 올리기 (.glb / .gltf, 50MB 이하)<input type="file" accept=".glb,.gltf" aria-label="3D 모델 올리기" onChange={upload} disabled={!enabled || busy}/></label>
      <label>내 모델<select value={selected} onChange={e => choose(e.currentTarget.value)} aria-label="내 3D 모델">
        <option value="">{models && models.length === 0 ? '올린 모델이 없습니다' : '선택'}</option>
        {(models ?? []).map(m => <option key={m.asset_id} value={m.asset_id}>{m.original_filename}</option>)}</select></label>
      <label>배경<select value={background} onChange={e => setBackground(e.currentTarget.value)} aria-label="무대 배경">
        {BACKGROUNDS.map(b => <option key={b.value} value={b.value}>{b.label}</option>)}</select></label>
    </div>
    {viewerError && <div className="auth-error" role="alert">{viewerError}</div>}
    <div data-testid="three-d-stage" data-model={selected} data-background={background}>
      <Studio3DViewer label="3D 모델 보기" background={background} showGrid modelUrl={modelUrl} accessToken={accessToken} onError={setViewerError}/>
    </div>
  </section>;
}
