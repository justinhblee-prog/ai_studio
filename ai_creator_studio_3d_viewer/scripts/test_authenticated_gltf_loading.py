from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
viewer = (ROOT / "src/Studio3DViewer.tsx").read_text()
workspace = (ROOT / "src/AssetWorkspace.tsx").read_text()

checks = {
    "authenticated bearer header": "Authorization: `Bearer ${accessToken}`" in viewer,
    "no-store authenticated fetch": "cache: 'no-store'" in viewer,
    "request abort on model change/unmount": "controller.abort()" in viewer and "signal: controller.signal" in viewer,
    "parse fetched bytes instead of loader URL request": "loader.parse(" in viewer and "loader.load(" not in viewer,
    "late GLTF parse errors use shared cancellation guard": "// GLTFLoader.parse is not abortable." in viewer and "reportGltfParseError({" in viewer,
    "shared parse-error helper guards before state mutation": "if (cancelled) return false;" in (ROOT / "src/reportGltfParseError.mjs").read_text(),
    "relative and absolute model URLs resolve against page URL": "resolveModelBasePath(modelUrl, window.location.href)" in viewer and "resolveModelBasePath" in viewer,
    "only current immutable version selected": "nextVersions.find((version) => version.is_current)" in workspace,
    "AssetVersion content endpoint used": "/versions/${encodeURIComponent(currentVersion.version_id)}/preview-content" in workspace,
    "access token passed into viewer": "accessToken={accessToken}" in workspace,
    "late parsed GLTF resources disposed": "finalizeGltfLoad({" in viewer and "cancelled: !isCurrentRequest()," in viewer and "rollback: (failedGltf)" in viewer and "modelRequestGateRef.current.invalidate('model')" in viewer and "disposeGltfResources(failedGltf)" in viewer,
    "complete GLTF retained for lifecycle disposal": "gltfRef.current = gltf;" in viewer and "dispose-loaded-gltf" in viewer and "disposeViewerResources(gltfRef.current)" in viewer,
    "stage floor and grid have independent disposal scope": "stageGroupRef.current = stageGroup;" in viewer and "dispose-stage-resources" in viewer and "disposeViewerResources(stageGroupRef.current)" in viewer,
    "directional shadow render target disposed": "dispose-key-light-shadow" in viewer and "keyLightRef.current?.shadow.dispose()" in viewer,
    "animation mixer uncaches model root": "uncache-animation-root" in viewer and "mixer.uncacheRoot(modelRef.current)" in viewer and "uncache-previous-animation-root" in viewer and "previousMixer.uncacheRoot(previousModel)" in viewer,
    "skinned mesh skeleton resources disposed": "if (object.skeleton) skeletons.add(object.skeleton);" in (ROOT / "src/disposeGltfResources.mjs").read_text(),
    "external URI restrictions remain documented": "External glTF resource URIs are not allowed" in (ROOT.parent / "ai_creator_studio_backend_starter/app/assets/validation.py").read_text(),
}
failed = [name for name, passed in checks.items() if not passed]
for name, passed in checks.items():
    print(f"{'PASS' if passed else 'FAIL'} {name}")
if failed:
    raise SystemExit(f"{len(failed)} checks failed: {failed}")
print(f"Authenticated GLTF loading: {len(checks)}/{len(checks)} PASS")
