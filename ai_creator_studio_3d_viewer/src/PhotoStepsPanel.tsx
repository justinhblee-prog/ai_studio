import { useCallback, useEffect, useState } from 'react';
import { apiRequest } from './app/apiClient.mjs';
import { errorText } from './app/errorMessages.mjs';
import { currentVersionId, listVersions, modelContentUrl } from './app/threeDClient.mjs';
import { MAX_STEPS, STEP_DEFS, deletePreset, listPresets, moveStep, newStep, runPhotoSteps, savePreset, stepsFromPreset, summarizeRecords, validatePresetName, validateSteps } from './app/photoStepsClient.mjs';
import type { Preset, Step } from './app/photoStepsClient.mjs';

type Props = { apiBaseUrl: string; accessToken: string; workspaceId: string };
type Image = { asset_id: string; original_filename: string };

// R-044 A-3: local photo steps (auto crop / solid background / fit canvas). Runs on this server only; no AI service; the original is kept.
export default function PhotoStepsPanel({ apiBaseUrl, accessToken, workspaceId }: Props) {
  const [images, setImages] = useState<Image[]>([]);
  const [source, setSource] = useState('');
  const [steps, setSteps] = useState<Step[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<{ name: string; lines: string[]; preview: string; before: string } | null>(null);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [presetName, setPresetName] = useState('');
  const [note, setNote] = useState('');

  const load = useCallback(async () => {
    try { setImages((await apiRequest(apiBaseUrl, `/v1/assets?workspace_id=${encodeURIComponent(workspaceId)}&kind=image`, { token: accessToken }))?.items ?? []); }
    catch (reason) { setError(errorText(reason, '이미지 목록을 불러오지 못했습니다.')); }
  }, [apiBaseUrl, accessToken, workspaceId]);
  const loadPresets = useCallback(async () => {
    try { setPresets((await listPresets(apiBaseUrl, accessToken, workspaceId))?.items ?? []); }
    catch (reason) { setError(errorText(reason, '프리셋을 불러오지 못했습니다.')); }
  }, [apiBaseUrl, accessToken, workspaceId]);
  useEffect(() => { load(); loadPresets(); }, [load, loadPresets]);
  useEffect(() => () => { if (result?.preview) URL.revokeObjectURL(result.preview); if (result?.before) URL.revokeObjectURL(result.before); }, [result]);

  const blobUrl = async (assetId: string) => {
    const version = currentVersionId(await listVersions(apiBaseUrl, accessToken, assetId));
    if (!version) return '';
    const res = await fetch(modelContentUrl(apiBaseUrl, assetId, version), { headers: { Authorization: `Bearer ${accessToken}` } });
    return res.ok ? URL.createObjectURL(await res.blob()) : '';
  };
  const presetProblem = validatePresetName(presetName, presets);
  const savePresetNow = async () => {
    if (presetProblem || validateSteps(steps)) return;
    setError(''); setNote('');
    try { await savePreset(apiBaseUrl, accessToken, workspaceId, presetName, steps); setNote(`"${presetName.trim()}" 프리셋을 저장했습니다.`); setPresetName(''); await loadPresets(); }
    catch (reason) { setError(errorText(reason, '프리셋을 저장하지 못했습니다.')); }
  };
  const removePreset = async (preset: Preset) => {
    setError(''); setNote('');
    try { await deletePreset(apiBaseUrl, accessToken, workspaceId, preset.preset_id); await loadPresets(); }
    catch (reason) { setError(errorText(reason, '프리셋을 삭제하지 못했습니다.')); }
  };

  const edit = (index: number, key: string, raw: string, type: string) =>
    setSteps(list => list.map((s, i) => (i === index ? { ...s, [key]: type === 'int' ? (raw.trim() === '' ? NaN : Number(raw)) : raw } : s)));
  const problem = !source ? '이미지를 골라 주세요.' : validateSteps(steps);

  const run = async () => {
    if (problem || busy) return;
    setBusy(true); setError(''); setResult(null);
    try {
      const done = await runPhotoSteps(apiBaseUrl, accessToken, workspaceId, source, steps);
      const [preview, before] = await Promise.all([blobUrl(done.asset.asset_id), blobUrl(source)]);
      setResult({ name: done.asset.original_filename, lines: summarizeRecords(done.steps), preview, before });
      await load();
    } catch (reason) { setError(errorText(reason, '단계를 실행하지 못했습니다.')); } finally { setBusy(false); }
  };

  return <section className="module" aria-label="사진 단계 편집" style={{ minWidth: 0 }}>
    <h2>사진 단계 편집</h2>
    <p>자동 크롭·단색 배경·캔버스 맞춤을 순서대로 적용해 새 이미지로 저장합니다. 이 서버 안에서만 처리되며 외부 AI 서비스로 보내지 않고, 원본은 그대로 남습니다.</p>
    {error && <div className="auth-error" role="alert">{error}</div>}
    <label>원본 이미지<select value={source} onChange={e => setSource(e.currentTarget.value)} aria-label="편집할 이미지">
      <option value="">{images.length ? '선택' : '이미지가 없습니다'}</option>
      {images.map(i => <option key={i.asset_id} value={i.asset_id}>{i.original_filename}</option>)}</select></label>
    <div role="group" aria-label="브랜드 프리셋">
      <label>프리셋 적용<select value="" aria-label="저장된 프리셋" onChange={e => { const p = presets.find(x => x.preset_id === e.currentTarget.value); if (p) { setSteps(stepsFromPreset(p)); setNote(`"${p.name}" 프리셋을 적용했습니다.`); } }}>
        <option value="">{presets.length ? '프리셋 선택' : '저장된 프리셋이 없습니다'}</option>
        {presets.map(p => <option key={p.preset_id} value={p.preset_id}>{p.name}</option>)}</select></label>
      {presets.length > 0 && <ul aria-label="프리셋 목록">{presets.map(p => <li key={p.preset_id}>{p.name} <button type="button" className="outline" aria-label={`${p.name} 프리셋 삭제`} onClick={() => removePreset(p)}>삭제</button></li>)}</ul>}
    </div>
    {note && <div className="auth-notice" role="status">{note}</div>}
    <div role="group" aria-label="단계 추가">
      {Object.entries(STEP_DEFS).map(([op, def]) => <button key={op} type="button" className="outline" title={def.help} disabled={steps.length >= MAX_STEPS}
        onClick={() => setSteps(list => [...list, newStep(op)])}>＋ {def.label}</button>)}
    </div>
    <ol aria-label="적용할 단계">
      {steps.map((step, index) => { const def = STEP_DEFS[step.op]; return <li key={index}>
        <b>{def.label}</b> <small>{def.help}</small>
        <div>{def.params.map(p => <label key={p.key}>{p.label}
          {p.type === 'color'
            ? <input type="color" value={step[p.key]} onChange={e => edit(index, p.key, e.currentTarget.value, 'color')}/>
            : <input type="number" min={p.min} max={p.max} step={1} value={Number.isNaN(step[p.key]) ? '' : step[p.key]} onChange={e => edit(index, p.key, e.currentTarget.value, 'int')} style={{ maxWidth: '7rem' }}/>}
        </label>)}</div>
        <div>
          <button type="button" className="outline" aria-label={`${index + 1}번 단계 위로`} disabled={index === 0} onClick={() => setSteps(list => moveStep(list, index, -1))}>↑</button>
          <button type="button" className="outline" aria-label={`${index + 1}번 단계 아래로`} disabled={index === steps.length - 1} onClick={() => setSteps(list => moveStep(list, index, 1))}>↓</button>
          <button type="button" className="outline" aria-label={`${index + 1}번 단계 삭제`} onClick={() => setSteps(list => list.filter((_, i) => i !== index))}>삭제</button>
        </div></li>; })}
    </ol>
    {steps.length === 0 && <p role="status">아래에서 단계를 추가해 주세요.</p>}
    {problem && steps.length > 0 && <small role="status">{problem}</small>}
    <div role="group" aria-label="프리셋으로 저장">
      <input value={presetName} maxLength={60} placeholder="프리셋 이름" aria-label="프리셋 이름" onChange={e => setPresetName(e.currentTarget.value)}/>
      <button type="button" className="outline" disabled={!!presetProblem || !!validateSteps(steps)} onClick={savePresetNow}>현재 단계를 프리셋으로 저장</button>
    </div>
    <button type="button" className="primary" disabled={!!problem || busy} onClick={run}>{busy ? '처리 중…' : '실행해서 새 이미지로 저장'}</button>
    {result && <div role="status" aria-label="단계 실행 결과">
      <b>"{result.name}" 이(가) 내 자산에 저장되었습니다.</b>
      <ul>{result.lines.map(l => <li key={l}>{l}</li>)}</ul>
      <div role="group" aria-label="전후 비교" style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
        {result.before && <figure style={{ margin: 0, minWidth: 0 }}><figcaption>전(원본)</figcaption><img src={result.before} alt="편집 전 원본" style={{ maxWidth: '100%', height: 'auto', maxHeight: 320 }}/></figure>}
        {result.preview && <figure style={{ margin: 0, minWidth: 0 }}><figcaption>후(결과)</figcaption><img src={result.preview} alt="편집 결과 미리보기" style={{ maxWidth: '100%', height: 'auto', maxHeight: 320 }}/></figure>}
      </div>
    </div>}
  </section>;
}
