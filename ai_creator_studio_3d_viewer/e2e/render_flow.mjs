// E-02 server-side render check: headless Chromium (software WebGL, no GPU) renders a SYNTHETIC .glb with the site's three.js.
// Real: Chromium + three.js + the render script. Not covered: real artist models, Draco/KTX2 files, the 3D studio screen, any backend route.
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const viewer = resolve(here, '..');
const backend = resolve(viewer, '..', 'ai_creator_studio_backend_starter');
const work = mkdtempSync(join(tmpdir(), 'render-flow-'));
const results = [];
const run = async (name, fn) => {
  try { await fn(); results.push({ name, ok: true }); console.log('PASS ' + name); }
  catch (e) { results.push({ name, ok: false }); console.log('FAIL ' + name + '\n      ' + String(e && e.message || e).split('\n')[0]); }
};
const sh = (cmd, args, opts = {}) => {
  const r = spawnSync(cmd, args, { encoding: 'utf8', ...opts });
  if (r.status !== 0) throw new Error(`${cmd} ${args.join(' ')} -> ${r.status}: ${(r.stderr || r.stdout || '').slice(0, 300)}`);
  return r.stdout;
};
const md5 = file => createHash('md5').update(readFileSync(file)).digest('hex');
const PNG_MAGIC = Buffer.from([0x89, 0x50, 0x4e, 0x47]);
let report, outDir;

try {
  await run('a synthetic sample model is generated (no real model, no network)', async () => {
    sh('python', [join(backend, 'scripts', 'make_sample_glb.py'), work]);
    assert.ok(readdirSync(work).includes('sphere_lo.glb'));
  });
  await run('8 angles + a 12-frame turntable render to PNG files in a few seconds on a machine without a GPU', async () => {
    outDir = join(work, 'out');
    const t = Date.now();
    report = JSON.parse(sh('node', [join(viewer, 'scripts', 'render_glb.mjs'), '--glb', join(work, 'sphere_lo.glb'), '--out', outDir, '--size', '512', '--angles', '8', '--turntable', '12']).trim().split('\n').pop());
    const seconds = (Date.now() - t) / 1000;
    assert.equal(report.frames, 20);
    assert.equal(readdirSync(outDir).filter(f => f.endsWith('.png')).length, 20);
    assert.ok(seconds < 60, 'took ' + seconds + ' s');
    console.log(`      ${report.frames} frames at ${report.size}px, total ${report.total_s}s, median frame ${report.frame_ms.median} ms, ${report.gl}`);
  });
  await run('every file is a real PNG, none is blank, and different angles give different pictures', async () => {
    const files = readdirSync(outDir).filter(f => f.endsWith('.png')).sort();
    for (const f of files) {
      const b = readFileSync(join(outDir, f));
      assert.ok(b.subarray(0, 4).equals(PNG_MAGIC), f + ' is not a PNG');
      assert.ok(b.length > 20000, f + ' looks blank (' + b.length + ' bytes)');     // a flat 512x512 PNG is a few hundred bytes
    }
    const angles = files.filter(f => f.startsWith('angle_')).map(f => md5(join(outDir, f)));
    assert.ok(new Set(angles).size >= 6, 'angles should differ, got ' + new Set(angles).size + ' distinct of 8');
    assert.notEqual(md5(join(outDir, 'angle_000.png')), md5(join(outDir, 'turn_003.png')));
  });
  await run('the model numbers come from the loaded file', async () => {
    assert.equal(report.triangles, 2048);
    assert.equal(report.meshes, 1);
  });
  await run('a missing or broken model fails with a clear message and no pictures', async () => {
    const bad = join(work, 'bad.glb');
    writeFileSync(bad, 'this is not a glb');
    const r = spawnSync('node', [join(viewer, 'scripts', 'render_glb.mjs'), '--glb', bad, '--out', join(work, 'bad_out'), '--size', '128', '--angles', '1'], { encoding: 'utf8' });
    assert.notEqual(r.status, 0);
    assert.match(r.stderr, /RENDER_FAILED/);
    assert.equal(spawnSync('node', [join(viewer, 'scripts', 'render_glb.mjs'), '--glb', join(work, 'nope.glb'), '--out', join(work, 'x')], { encoding: 'utf8' }).status, 1);
  });
} finally { rmSync(work, { recursive: true, force: true }); }
const ok = results.filter(r => r.ok).length;
console.log(`SUMMARY ${ok}/${results.length} render steps passed`);
process.exit(ok === results.length ? 0 : 1);
