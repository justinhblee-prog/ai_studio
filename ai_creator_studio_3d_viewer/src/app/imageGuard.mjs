// R-035 (screen side, supporting only): make the EASY ways of taking a picture from the page harder, and mark review previews with the
// viewer's name and time. None of this stops a screenshot or a determined user; the real protection is on the server (signed short-lived
// links, authentication, roles, download audit).
const PROTECTED = 'img, canvas, [data-protect-image]';

export function isProtectedTarget(target) {
  return !!target && typeof target.closest === 'function' && !!target.closest(PROTECTED);
}

// Context menu (right click / long press) and drag-to-save are cancelled on pictures only; text and forms keep their normal behaviour.
export function blockIfProtected(event) {
  if (isProtectedTarget(event?.target)) { event.preventDefault(); return true; }
  return false;
}

export function installImageGuard(doc = globalThis.document) {
  if (!doc?.addEventListener) return () => undefined;
  doc.addEventListener('contextmenu', blockIfProtected);
  doc.addEventListener('dragstart', blockIfProtected);
  return () => { doc.removeEventListener('contextmenu', blockIfProtected); doc.removeEventListener('dragstart', blockIfProtected); };
}

const XML = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' };
export const watermarkText = (name, when = new Date()) => {
  const p = (n) => String(n).padStart(2, '0');
  const stamp = `${when.getFullYear()}-${p(when.getMonth() + 1)}-${p(when.getDate())} ${p(when.getHours())}:${p(when.getMinutes())}`;
  return `${String(name || '').trim().slice(0, 40) || '검수용'} · ${stamp}`;
};

// A faint, repeated, tilted text tile as a CSS background (SVG data URL). The text is XML-escaped: a name can never inject markup.
export function watermarkStyle(text) {
  const safe = String(text).replace(/[&<>"']/g, (c) => XML[c]);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180"><text x="20" y="110" transform="rotate(-24 160 90)" font-family="sans-serif" font-size="14" fill="#000" fill-opacity="0.16" stroke="#fff" stroke-opacity="0.12">${safe}</text></svg>`;
  return { backgroundImage: `url("data:image/svg+xml;utf8,${encodeURIComponent(svg)}")`, backgroundRepeat: 'repeat' };
}
