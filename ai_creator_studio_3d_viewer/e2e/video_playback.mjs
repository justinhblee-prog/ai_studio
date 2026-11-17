// Lane 4: does a real browser PLAY the MP4 that app/video_mp4.py makes?   node e2e/video_playback.mjs <file.mp4>
// The file is served from a local page and played (muted) in two browsers:
//   - Google Chrome (the browser people use; it has the H.264 decoder)  -> these checks decide the result
//   - the Chromium that Playwright downloads (may lack H.264)           -> reported as INFO only, never counted
// No backend, no login, no network beyond 127.0.0.1.
import { createServer } from 'node:http';
import { readFileSync } from 'node:fs';
import { chromium } from './harness.mjs';

const file = process.argv[2];
if (!file) { console.log('usage: node e2e/video_playback.mjs <file.mp4>'); process.exit(2); }
const mp4 = readFileSync(file);
const page_html = '<!doctype html><meta charset="utf-8"><title>video playback check</title><video id="v" src="/sample.mp4" muted playsinline></video>';
const server = createServer((req, res) => {
  if (req.url === '/sample.mp4') { res.writeHead(200, { 'Content-Type': 'video/mp4', 'Content-Length': mp4.length }); res.end(mp4); }
  else { res.writeHead(200, { 'Content-Type': 'text/html' }); res.end(page_html); }
});
await new Promise((done) => server.listen(0, '127.0.0.1', done));
const url = `http://127.0.0.1:${server.address().port}/`;

async function play(options) {
  let browser;
  try { browser = await chromium.launch(options); } catch (error) { return { launched: false, reason: String(error.message).split('\n')[0] }; }
  try {
    const page = await browser.newPage();
    await page.goto(url);
    return await page.evaluate(async () => {
      const v = document.getElementById('v');
      const out = { launched: true, canPlayType: v.canPlayType('video/mp4; codecs="avc1.640028"'), loaded: false, error: null };
      const ready = await new Promise((done) => {
        if (v.readyState >= 2) return done('loaded');
        v.addEventListener('loadeddata', () => done('loaded'), { once: true });
        v.addEventListener('error', () => done('error'), { once: true });
        setTimeout(() => done('timeout'), 15000);
      });
      if (ready !== 'loaded') { out.error = ready + (v.error ? ` code ${v.error.code}` : ''); return out; }
      out.loaded = true; out.width = v.videoWidth; out.height = v.videoHeight; out.duration = v.duration;
      try { await v.play(); } catch (e) { out.error = 'play: ' + e.message; return out; }
      await new Promise((done) => setTimeout(done, 1500));
      out.currentTime = v.currentTime;
      const canvas = document.createElement('canvas'); canvas.width = 160; canvas.height = 90;
      const ctx = canvas.getContext('2d'); ctx.drawImage(v, 0, 0, 160, 90);
      const px = ctx.getImageData(0, 0, 160, 90).data; let lo = 255, hi = 0;
      for (let i = 0; i < px.length; i += 4) { const y = (px[i] + px[i + 1] + px[i + 2]) / 3; if (y < lo) lo = y; if (y > hi) hi = y; }
      out.brightnessRange = Math.round(hi - lo);
      return out;
    });
  } finally { await browser.close(); }
}

const chrome = await play({ channel: 'chrome' });
const bundled = await play({});
server.close();
console.log('RESULT google-chrome ' + JSON.stringify(chrome));
console.log('INFO playwright-chromium (not counted) ' + JSON.stringify(bundled));

const checks = [
  ['Chrome starts and loads the video data', chrome.launched && chrome.loaded === true],
  ['the picture size and length are the ones that were encoded (1280x720, 5 s)', chrome.width === 1280 && chrome.height === 720 && Math.abs(chrome.duration - 5) < 0.2],
  ['playback moves forward', typeof chrome.currentTime === 'number' && chrome.currentTime > 0.3],
  ['a real picture is painted (not one flat colour)', typeof chrome.brightnessRange === 'number' && chrome.brightnessRange > 40],
];
let passed = 0;
for (const [name, ok] of checks) { console.log(`${ok ? 'PASS' : 'FAIL'} ${name}`); if (ok) passed += 1; }
console.log(`SUMMARY ${passed}/${checks.length} video playback checks passed`);
process.exit(passed === checks.length ? 0 : 1);
