// R-042: the company usage screen's logic. Numbers come from GET /v1/workspaces/{id}/usage (no provider prices are ever in it).
import { apiRequest } from './apiClient.mjs';

export const monthLabel = (date) => `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, '0')}`;

// "이번 달" and "지난 달" (UTC, like the server).
export function monthOptions(now = new Date()) {
  const last = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - 1, 1));
  return [{ value: monthLabel(now), label: '이번 달' }, { value: monthLabel(last), label: '지난 달' }];
}

export const fetchUsage = (api, token, workspaceId, month) =>
  apiRequest(api, `/v1/workspaces/${encodeURIComponent(workspaceId)}/usage?month=${encodeURIComponent(month)}`, { token });

// Real calls stop at 90% of the limit (server rule), so "100%" on screen means that stop line has been reached.
export function limitBanner(counted, limit) {
  if (!Number.isInteger(counted) || !Number.isInteger(limit) || limit <= 0) return null;
  if (counted >= Math.max(1, Math.floor(limit * 0.9))) return { level: 100, text: `이번 달 생성 한도에 도달했습니다 (${counted}/${limit}건). 다음 달에 다시 시도해 주세요.` };
  if (counted >= Math.ceil(limit * 0.8)) return { level: 80, text: `이번 달 한도의 80%를 넘었습니다 (${counted}/${limit}건).` };
  return null;
}

// CSV for the member table: values that a spreadsheet would run as a formula are neutralised.
const cell = (value) => {
  let text = String(value ?? '');
  if (/^[=+\-@\t\r]/.test(text)) text = `'${text}`;
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
};
export function usageCsv(usage) {
  const services = Object.keys(usage?.services ?? {}).sort();
  const lines = [['user_id', 'jobs', 'failed', ...services].map(cell).join(',')];
  for (const m of usage?.members ?? []) lines.push([m.user_id, m.jobs, m.failed, ...services.map((s) => m.services?.[s] ?? 0)].map(cell).join(','));
  return `${lines.join('\r\n')}\r\n`;
}
