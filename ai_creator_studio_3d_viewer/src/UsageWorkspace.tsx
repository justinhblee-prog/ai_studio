import { useCallback, useEffect, useMemo, useState } from 'react';
import { errorText } from './app/errorMessages.mjs';
import { fetchUsage, limitBanner, monthOptions, usageCsv } from './app/usageClient.mjs';
import type { Usage } from './app/usageClient.mjs';

type Props = { apiBaseUrl: string; accessToken: string; workspaceId: string };

const SERVICE_LABELS: Record<string, string> = { tryon: '가상 착용', photo: '포토', character: '캐릭터', three_d: '3D', video: '영상', market: '마켓' };

// R-042: usage of this workspace. Owners and admins see the whole company and every member; everyone else sees only their own numbers.
export default function UsageWorkspace({ apiBaseUrl, accessToken, workspaceId }: Props) {
  const months = useMemo(() => monthOptions(), []);
  const [month, setMonth] = useState(months[0].value);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setError('');
    try { setUsage(await fetchUsage(apiBaseUrl, accessToken, workspaceId, month)); }
    catch (reason) { setUsage(null); setError(errorText(reason, '사용량을 불러오지 못했습니다.')); }
  }, [apiBaseUrl, accessToken, workspaceId, month]);
  useEffect(() => { setUsage(null); load(); }, [load]);

  const whole = usage?.scope === 'workspace';
  const banner = whole && month === months[0].value ? limitBanner(usage?.limit?.counted_against_limit, usage?.limit?.monthly_jobs) : null;
  const download = () => {
    if (!usage) return;
    const url = URL.createObjectURL(new Blob(['﻿', usageCsv(usage)], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url; link.download = `usage-${usage.month}.csv`; link.click();
    URL.revokeObjectURL(url);
  };

  return <section className="module" aria-label="사용량">
    <div className="module-head"><div><small>USAGE</small><h1>사용량</h1>
      <p>{whole ? '이 작업공간 전체와 구성원별 사용 건수입니다.' : '내 사용 건수입니다. 작업공간 전체는 소유자·관리자만 볼 수 있습니다.'}</p></div>
      <label>기간 <select value={month} onChange={event => setMonth(event.currentTarget.value)}>{months.map(m => <option key={m.value} value={m.value}>{m.label} ({m.value})</option>)}</select></label></div>
    {error && <div className="auth-error" role="alert">{error} <button type="button" className="outline" onClick={load}>다시 시도</button></div>}
    {banner && <div className={banner.level === 100 ? 'auth-error' : 'warning'} role="status" aria-label="한도 안내">{banner.text}</div>}
    {usage && <>
      <div className="auth-notice" role="status" aria-label="사용량 요약">
        <div>기간: <b>{usage.month}</b> · 범위: <b>{whole ? '작업공간 전체' : '나'}</b></div>
        <div>작업 건수: <b data-testid="usage-jobs">{usage.jobs}</b>건{usage.failed ? <> · 실패 {usage.failed}건(건수에 넣지 않음)</> : null}</div>
        {Object.entries(usage.services).map(([key, n]) => <div key={key}>{SERVICE_LABELS[key] ?? key}: {n}건</div>)}
        {whole && usage.limit?.monthly_jobs ? <div>월 한도: {usage.limit.counted_against_limit ?? 0}/{usage.limit.monthly_jobs}건 <small>(시험 생성은 한도에 세지 않습니다)</small></div> : null}
      </div>
      <table aria-label="구성원별 사용량"><thead><tr><th>사용자</th><th>작업 건수</th><th>실패</th></tr></thead>
        <tbody>{usage.members.length === 0 ? <tr><td colSpan={3}>이 기간의 사용 기록이 없습니다.</td></tr>
          : usage.members.map(m => <tr key={m.user_id}><td>{m.user_id}</td><td>{m.jobs}</td><td>{m.failed}</td></tr>)}</tbody></table>
      {whole && <p><button type="button" className="outline" onClick={download}>CSV 내보내기</button></p>}
    </>}
  </section>;
}
