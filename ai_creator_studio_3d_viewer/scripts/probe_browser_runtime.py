#!/usr/bin/env python3
"""Optional real-browser WebGL2 capability smoke test (not a Viewer E2E test)."""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: Python Playwright is not installed; this optional probe was not run.", file=sys.stderr)
        return 2

    executable = os.environ.get("CHROMIUM_EXECUTABLE") or shutil.which("chromium") or shutil.which("google-chrome")
    if not executable:
        print("ERROR: Chromium executable not found; set CHROMIUM_EXECUTABLE.", file=sys.stderr)
        return 2
    args = [
        "--no-sandbox",
        "--enable-webgl",
        "--enable-unsafe-swiftshader",
        "--use-gl=angle",
        "--use-angle=swiftshader",
        "--disable-gpu-sandbox",
        "--ignore-gpu-blocklist",
    ]
    html = r"""<!doctype html><html><body><canvas id="probe" width="64" height="64"></canvas>
<script>
window.__probe = { resizeObserved: false, animationFrame: false, webgl2: false, trianglePixel: false, contextLost: false, contextRestored: false, renderer: null, error: null };
const canvas = document.getElementById('probe');
const observer = new ResizeObserver(() => { window.__probe.resizeObserved = true; });
observer.observe(canvas);
requestAnimationFrame(() => { window.__probe.animationFrame = true; });
const gl = canvas.getContext('webgl2', { antialias: false, preserveDrawingBuffer: true });
if (gl) {
  window.__probe.webgl2 = true;
  const vertexSource = `#version 300 es\nin vec2 position;\nvoid main(){gl_Position=vec4(position,0.0,1.0);}`;
  const fragmentSource = `#version 300 es\nprecision highp float;\nout vec4 color;\nvoid main(){color=vec4(0.2,0.7,0.9,1.0);}`;
  const compile = (type, source) => {
    const shader = gl.createShader(type); gl.shaderSource(shader, source); gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(shader));
    return shader;
  };
  try {
    const program = gl.createProgram();
    gl.attachShader(program, compile(gl.VERTEX_SHADER, vertexSource));
    gl.attachShader(program, compile(gl.FRAGMENT_SHADER, fragmentSource));
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program));
    gl.useProgram(program);
    const buffer = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-0.8,-0.8, 0.8,-0.8, 0.0,0.8]), gl.STATIC_DRAW);
    const location = gl.getAttribLocation(program, 'position');
    gl.enableVertexAttribArray(location); gl.vertexAttribPointer(location, 2, gl.FLOAT, false, 0, 0);
    gl.viewport(0, 0, canvas.width, canvas.height); gl.clearColor(0,0,0,1); gl.clear(gl.COLOR_BUFFER_BIT);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    const pixel = new Uint8Array(4); gl.readPixels(32, 32, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
    window.__probe.trianglePixel = pixel[2] > 100 && pixel[1] > 50;
    window.__probe.renderer = gl.getParameter(gl.RENDERER);
    const loseContext = gl.getExtension('WEBGL_lose_context');
    if (loseContext) {
      canvas.addEventListener('webglcontextlost', (event) => {
        event.preventDefault();
        window.__probe.contextLost = true;
        setTimeout(() => loseContext.restoreContext(), 0);
      }, { once: true });
      canvas.addEventListener('webglcontextrestored', () => {
        window.__probe.contextRestored = !gl.isContextLost();
      }, { once: true });
      loseContext.loseContext();
    }
  } catch (error) { window.__probe.error = String(error); }
} else {
  window.__probe.error = 'WebGL2 context unavailable';
}
</script></body></html>"""

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=executable, headless=True, args=args)
            page = browser.new_page()
            page.set_content(html)
            wait_error = None
            try:
                page.wait_for_function("window.__probe.animationFrame && window.__probe.resizeObserved && window.__probe.contextLost && window.__probe.contextRestored", timeout=8000)
            except Exception as error:
                wait_error = str(error)
            result = page.evaluate("window.__probe")
            browser.close()
    except Exception as error:  # browser launch/context failures are environment diagnostics
        print(json.dumps({"status": "blocked", "error": str(error)}, indent=2))
        return 2

    result["chromium_executable"] = executable
    if wait_error:
        result["wait_error"] = wait_error
    result["status"] = "pass" if result["webgl2"] and result["trianglePixel"] and result["resizeObserved"] and result["animationFrame"] and result["contextLost"] and result["contextRestored"] and not result["error"] else "blocked"
    result["scope"] = "browser capability smoke only; does not load the React/Three.js Viewer"
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
