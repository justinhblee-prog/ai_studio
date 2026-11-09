from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "src" / "Studio3DViewer.tsx").read_text()
helper = (ROOT / "src" / "runViewerCleanupSteps.mjs").read_text()

assert "import { runViewerCleanupSteps } from './runViewerCleanupSteps.mjs'" in source
# A missing/failed WebGL implementation must render the Viewer error state,
# rather than throwing from the React effect before cleanup can be registered.
renderer_guard = source[source.index('// WebGLRenderer construction'):source.index('renderer.setPixelRatio', source.index('// WebGLRenderer construction'))]
assert 'let renderer: THREE.WebGLRenderer' in renderer_guard
assert 'try {' in renderer_guard and 'new THREE.WebGLRenderer' in renderer_guard
assert "setLoadState('error')" in renderer_guard
assert 'return;' in renderer_guard
assert "notifyViewerError(onErrorRef.current, message)" in renderer_guard
assert "import { notifyViewerError } from './notifyViewerError.mjs'" in source
assert source.count('notifyViewerError(onErrorRef.current, message)') == 7
assert source.count("runViewerCleanupSteps([") == 2
teardown = source[source.index("return () => {", source.index("const animationLoop =")):source.index("// grid visibility")]
ordered = [
    "cancel-animation-frame", "disconnect-resize-observer", "dispose-orbit-controls",
    "stop-animation-actions", "uncache-animation-root", "dispose-loaded-gltf",
    "dispose-stage-resources", "dispose-key-light-shadow", "dispose-webgl-renderer",
    "remove-renderer-canvas", "clear-viewer-references",
]
positions = [teardown.index(name) for name in ordered]
assert positions == sorted(positions)
replacement = source[source.index("const previousModel ="):source.index("if (!modelUrl)")]
replacement_order = ["remove-previous-model", "stop-previous-animation", "uncache-previous-animation-root", "dispose-previous-gltf", "clear-previous-model-references"]
positions = [replacement.index(name) for name in replacement_order]
assert positions == sorted(positions)
assert "catch (error)" in helper and "errors.push" in helper
assert "completedCount" in helper and "attemptedCount" in helper
assert "onError(result)" in helper
assert source.count("console.error('[AI CREATOR STUDIO]") == 8
assert "import { createResourceRollback } from './resourceRollback.mjs'" in source
assert "rollback.defer('dispose-webgl-renderer'" in source
assert "rollback.defer('disconnect-resize-observer'" in source
assert "rollback.defer('remove-webgl-context-listeners'" in source
assert 'rollback.commit();' in source
assert 'rollback.rollback(' in source
assert "setLoadState('error')" in source[source.index('} catch (error) {', source.index('rollback.commit();')):source.index('// grid visibility')]
print("Viewer cleanup lifecycle structural: 20/20 passed")

# Integration disposal wrapper must surface collected resource errors to the
# failure-isolated cleanup runner, while still using the exhaustive disposer.
disposer = (ROOT / "src" / "disposeViewerResources.mjs").read_text()
assert "disposeGltfResources(resources)" in disposer
assert "result.errors.length > 0" in disposer
assert "throw new Error" in disposer
assert source.count("disposeViewerResources(") >= 3
print("Viewer disposal diagnostic integration: 4/4 passed")
