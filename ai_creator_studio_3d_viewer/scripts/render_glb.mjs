// E-02 step 1: SERVER-SIDE render of a .glb with headless Chromium + the SAME three.js the site uses (same look as the viewer, no GPU needed: software WebGL).
// Usage: node scripts/render_glb.mjs --glb model.glb --out outdir [--size 768] [--angles 8] [--elevation 20] [--turntable 24]
// Writes angle_000.png ... and, with --turntable N, turn_000.png ... (a 360-degree set for a rotation cut); prints a JSON timing report. No network, no secrets.
import { createServer } from 'node:http';
import { createReadStream, existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, extname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');
const require = createRequire(import.meta.url);

function args() {
  const a = process.argv.slice(2), o = { size: 768, angles: 8, elevation: 20, turntable: 0 };
  for (let i = 0; i < a.length; i += 2) o[a[i].replace(/^--/, '')] = a[i + 1];
  for (const k of ['size', 'angles', 'elevation', 'turntable']) o[k] = Number(o[k]);
  if (!o.glb || !o.out) throw new Error('usage: --glb <file> --out <dir>');
  return o;
}

const PAGE = `<!doctype html><meta charset="utf-8"><body style="margin:0;background:#fff">
<script type="importmap">{"imports":{"three":"/three/build/three.module.js","three/addons/":"/three/examples/jsm/"}}</script>
<canvas id="c"></canvas>
<script type="module">
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
const t0 = performance.now();
window.__ready = (async () => {
  const size = window.__size;
  const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('c'), antialias: true, preserveDrawingBuffer: true, alpha: false });
  renderer.setSize(size, size, false); renderer.setPixelRatio(1); renderer.setClearColor(0xf2f2f2, 1);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  const scene = new THREE.Scene();
  scene.add(new THREE.HemisphereLight(0xffffff, 0x8a8a96, 1.1));
  const sun = new THREE.DirectionalLight(0xffffff, 2.2); sun.position.set(3, 5, 4); scene.add(sun);
  const loader = new GLTFLoader(); loader.setMeshoptDecoder(MeshoptDecoder);
  const tLoad = performance.now();
  const gltf = await loader.loadAsync('/model.glb');
  const loadMs = performance.now() - tLoad;
  scene.add(gltf.scene);
  const box = new THREE.Box3().setFromObject(gltf.scene), sphere = box.getBoundingSphere(new THREE.Sphere());
  const camera = new THREE.PerspectiveCamera(35, 1, sphere.radius / 50, sphere.radius * 50);
  const dist = sphere.radius / Math.sin(THREE.MathUtils.degToRad(35) / 2) * 1.05;
  let triangles = 0, meshes = 0;
  gltf.scene.traverse(o => { if (o.isMesh) { meshes++; const g = o.geometry; triangles += (g.index ? g.index.count : g.attributes.position.count) / 3; } });
  window.__shot = (deg, elev) => {
    const a = THREE.MathUtils.degToRad(deg), e = THREE.MathUtils.degToRad(elev);
    camera.position.set(sphere.center.x + dist * Math.cos(e) * Math.sin(a), sphere.center.y + dist * Math.sin(e), sphere.center.z + dist * Math.cos(e) * Math.cos(a));
    camera.lookAt(sphere.center); camera.updateMatrixWorld();
    const t = performance.now(); renderer.render(scene, camera);
    const url = renderer.domElement.toDataURL('image/png'); const ms = performance.now() - t;
    return { url, ms };
  };
  window.__info = { loadMs, triangles, meshes, gl: renderer.getContext().getParameter(renderer.getContext().VERSION), startMs: performance.now() - t0 };
  return true;
})().catch(e => { window.__error = String(e && e.stack || e); return false; });
</script>`;

function serve(glb) {
  const types = { '.js': 'text/javascript', '.mjs': 'text/javascript', '.html': 'text/html', '.glb': 'model/gltf-binary', '.wasm': 'application/wasm' };
  return new Promise(resolveServer => {
    const server = createServer((req, res) => {
      const path = decodeURIComponent(new URL(req.url, 'http://x').pathname);
      if (path === '/' || path === '/index.html') { res.writeHead(200, { 'content-type': 'text/html' }); return res.end(PAGE); }
      let file = null;
      if (path === '/model.glb') file = glb;
      else if (path.startsWith('/three/')) file = join(root, 'node_modules', 'three', path.slice(7));
      if (!file || !file.startsWith(path === '/model.glb' ? glb : join(root, 'node_modules', 'three')) || !existsSync(file) || !statSync(file).isFile()) { res.writeHead(404); return res.end('not found'); }
      res.writeHead(200, { 'content-type': types[extname(file)] || 'application/octet-stream' });
      createReadStream(file).pipe(res);
    }).listen(0, '127.0.0.1', () => resolveServer(server));
  });
}

async function main() {
  const o = args();
  const glb = resolve(o.glb);
  if (!existsSync(glb)) throw new Error('no such file: ' + glb);
  mkdirSync(o.out, { recursive: true });
  const { chromium } = require('playwright');
  const server = await serve(glb);
  const t0 = Date.now();
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const launchMs = Date.now() - t0;
  try {
    const page = await browser.newPage({ viewport: { width: o.size, height: o.size } });
    await page.addInitScript(size => { window.__size = size; }, o.size);
    const tPage = Date.now();
    await page.goto(`http://127.0.0.1:${server.address().port}/`);
    await page.waitForFunction(() => window.__ready !== undefined);
    const ok = await page.evaluate(() => window.__ready);
    if (!ok) throw new Error('page failed: ' + await page.evaluate(() => window.__error));
    const pageMs = Date.now() - tPage;
    const info = await page.evaluate(() => window.__info);
    const frames = [];
    const shoot = async (name, deg) => {
      const { url, ms } = await page.evaluate(([d, e]) => window.__shot(d, e), [deg, o.elevation]);
      const png = Buffer.from(url.split(',')[1], 'base64');
      writeFileSync(join(o.out, name), png);
      frames.push({ name, bytes: png.length, render_ms: Math.round(ms * 10) / 10 });
    };
    for (let i = 0; i < o.angles; i++) await shoot(`angle_${String(i).padStart(3, '0')}.png`, (360 / o.angles) * i);
    for (let i = 0; i < o.turntable; i++) await shoot(`turn_${String(i).padStart(3, '0')}.png`, (360 / o.turntable) * i);
    const sizes = frames.map(f => f.bytes), times = frames.map(f => f.render_ms).sort((a, b) => a - b);
    const report = { glb: o.glb, size: o.size, elevation: o.elevation, chromium_launch_ms: launchMs, page_load_ms: pageMs, gl: info.gl, glb_load_ms: Math.round(info.loadMs), meshes: info.meshes,
      triangles: info.triangles, frames: frames.length, frame_ms: { min: times[0], median: times[Math.floor(times.length / 2)], max: times[times.length - 1] },
      png_bytes_min: Math.min(...sizes), png_bytes_max: Math.max(...sizes), total_s: Math.round((Date.now() - t0) / 100) / 10 };
    writeFileSync(join(o.out, 'report.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report));
  } finally {
    await browser.close();
    server.close();
  }
}
main().catch(e => { console.error('RENDER_FAILED', e && e.stack || e); process.exit(1); });
