"""Offline structural checks for the Three.js viewer source (not a TS/browser test)."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / "src/Studio3DViewer.tsx").read_text(encoding="utf-8")
checks = {
    "Three.js WebGL renderer": "new THREE.WebGLRenderer" in source,
    "GLTF/GLB loader": "new GLTFLoader()" in source and "loader.parse(" in source and "readModelResponse(response" in source,
    "Orbit controls": "new OrbitControls(" in source,
    "camera reset": "const resetCamera" in source,
    "grid toggle": "setGridVisible" in source,
    "resize observer": "new ResizeObserver" in source,
    "animation loop cleanup": "cancelAnimationFrame(frameId)" in source,
    "scene readiness reload": "[modelUrl, accessToken, sceneVersion]" in source and "sceneVersion === 0" in source,
    "stale callback protection": "onLoadRef.current" in source and "onErrorRef.current" in source,
    "texture/material/geometry/skeleton disposal": "disposeGltfResources" in source and "disposeViewerResources" in source and all(value in (root / "src/disposeGltfResources.mjs").read_text() for value in ("textures", "materials", "geometries", "skeletons")),
    "glTF animation mixer": "new THREE.AnimationMixer(model)" in source,
    "animation frame updates": "mixerRef.current?.update(clock.getDelta())" in source,
    "animation controls": "setAnimationPlaying" in source and "애니메이션" in source,
    "animation cleanup": "mixer?.stopAllAction()" in source and "mixer.uncacheRoot(modelRef.current)" in source,
}
workspace = (root / "src/AssetWorkspace.tsx").read_text(encoding="utf-8")
workspace_checks = {
    "authenticated asset upload": "Authorization: `Bearer ${accessToken}`" in workspace and "form.set('file', file)" in workspace,
    "owner-scoped asset listing": "workspace_id=${encodeURIComponent(workspaceId)}" in workspace,
    "authenticated immutable preview content integration": "/preview-content`" in workspace and "loadVersions(assetId, controller.signal)" in workspace,
    "asset deletion integration": "method: 'DELETE'" in workspace,
    "viewer receives signed model URL": "<Studio3DViewer modelUrl={previewUrl}" in workspace,
    "asset version history retrieval": "/versions`" in workspace and "loadVersions" in workspace,
    "verified historical version restore action": "/restore`" in workspace and "이 버전으로 복원" in workspace,
    "3D workspace excludes source images": "&kind=model" in workspace,
    "Asset Workspace aborts stale workspace loads": "new AbortController()" in workspace and "return () => {" in workspace and "controller.abort()" in workspace and "signal?.aborted" in workspace,
    "Asset Workspace ignores stale asset-selection responses": "selectionRequestRef" in workspace and "requestId === selectionRequestRef.current" in workspace and "isSelectionCurrent" in workspace,
    "Asset selection aborts superseded and unmounted preview/version requests": all(value in workspace for value in ("selectionControllerRef.current?.abort()", "controller.signal.aborted", "loadVersions(assetId, controller.signal)", "isScopeCurrent(scope)", "selectionControllerRef.current = null")),
    "Asset deletion invalidates a pending selection for the removed asset": "selectionRequestRef.current += 1;\n        selectionControllerRef.current?.abort();" in workspace,
    "Asset restore invalidates the old signed preview and version history before rehydration": all(value in workspace for value in ("The restored version changes the current immutable version pointer.", "setPreviewUrl(null);\n      setVersions([]);", "await loadAssets();\n      if (!isScopeCurrent(scope)) return;\n      await selectAsset(assetId);")),
}
checks.update(workspace_checks)
photo_workspace = (root / "src/PhotoDraftWorkspace.tsx").read_text(encoding="utf-8")
photo_checks = {
    "Photo Draft reads private image assets": "kind=image" in photo_workspace and "/v1/assets/images" in photo_workspace,
    "Photo Draft create and archive API integration": "/v1/photo-drafts" in photo_workspace and "/archive?workspace_id=" in photo_workspace,
    "Photo Draft exposes constrained editing options": all(value in photo_workspace for value in ("ENHANCE", "BACKGROUND", "LIGHTING", "RETOUCH", "COMPOSE")),
    "Photo Draft UI clearly distinguishes deterministic local processing from AI": all(value in photo_workspace for value in ("Pillow 기반 결정론적 로컬 이미지 조정", "생성형 AI 아님", "Provider 호출과 크레딧 차감은 실행되지 않습니다")),
    "Photo Draft UI executes only supported local operations": all(value in photo_workspace for value in ("process-local?workspace_id=", "로컬 이미지 처리 실행", "draft.input.operation === 'ENHANCE'", "draft.input.operation === 'LIGHTING'")),
    "Photo Draft UI displays local run output and semantic review limits": all(value in photo_workspace for value in ("output_asset_id", "output_version_id", "semantic_identity_preservation_verified")),
    "Photo Draft UI supports output review and gated manifest export": all(value in photo_workspace for value in ("reviewRun(draft.draft_id, run.run_id, 'approve')", "reviewRun(draft.draft_id, run.run_id, 'request-changes')", "reviewRun(draft.draft_id, run.run_id, 'reject')", "/export-manifest?workspace_id=")),
    "Photo Draft UI displays output review state": "결과 검수 상태" in photo_workspace and "승인 결과 manifest 내보내기" in photo_workspace,
    "Photo Draft UI previews exact source and output AssetVersions with authenticated fetch": all(value in photo_workspace for value in ("/versions/${encodeURIComponent(versionId)}/preview-content", "draft.input.source_version_id", "run.output_version_id", "immutable AssetVersion")),
    "Photo Draft UI discloses metadata-only export and no rights grant": "게시·상업적 이용 권리를 부여하지 않습니다" in photo_workspace,
    "Photo Draft aborts stale workspace reads": "new AbortController()" in photo_workspace and "return () => controller.abort()" in photo_workspace and "signal?.aborted" in photo_workspace,
    "Photo Draft ignores out-of-order nested reload hydration": "loadSequenceRef" in photo_workspace and photo_workspace.count("requestId !== loadSequenceRef.current") >= 2,
    "Photo Draft preview requests are latest-per-AssetVersion": all(value in photo_workspace for value in ("KeyedRequestGate", "previewRequestGateRef.current.next(previewKey)", "isCurrent(previewKey, previewRequestId)")),
    "Photo Draft scope reset invalidates pending preview requests": "previewRequestGateRef.current.invalidateAll()" in photo_workspace,
    "Photo Draft review/archive/manifest mutations are serialized": all(value in photo_workspace for value in ("reviewMutationInFlightRef.current", "setManifestJson(null); setReviewComment('')", "reviewMutationInFlightRef.current = false")),
}
checks.update(photo_checks)
checks["Photo Draft owns and revokes authenticated preview object URLs"] = "AuthenticatedPreviewObjectUrls" in photo_workspace and "previewObjectUrlsRef.current.clear()" in photo_workspace
lookbook_workspace = (root / "src/LookbookDraftWorkspace.tsx").read_text(encoding="utf-8")
lookbook_checks = {
    "Lookbook UI loads workspace image and project references": all(value in lookbook_workspace for value in ("kind=image", "/v1/projects?workspace_id=", "/characters`")),
    "Lookbook UI creates and archives drafts": "/v1/lookbook-drafts" in lookbook_workspace and "/archive?workspace_id=" in lookbook_workspace,
    "Lookbook UI selects multiple products and optional person assets": "product_asset_ids: productAssetIds" in lookbook_workspace and "multiple size={4}" in lookbook_workspace and "person_asset_id: personAssetId || null" in lookbook_workspace,
    "Lookbook UI distinguishes approved assembly from unavailable AI generation": all(value in lookbook_workspace for value in ("개별 승인된 Photo 결과 AssetVersion 연결", "새로운 사진 생성/AI Provider 호출", "조립 순서는 별도 검토·승인 후에만 내보낼 수 있습니다")),
    "Lookbook aborts stale workspace reads": "new AbortController()" in lookbook_workspace and "return () => controller.abort()" in lookbook_workspace and "signal?.aborted" in lookbook_workspace,
}
checks.update(lookbook_checks)
product_workspace = (root / "src/ProductCatalogWorkspace.tsx").read_text(encoding="utf-8")
product_checks = {
    "Product Catalog UI creates and archives SKU records": "/v1/products" in product_workspace and "/archive?workspace_id=" in product_workspace,
    "Product Catalog UI edits SKU metadata and image references with PUT": all(value in product_workspace for value in ("editingProductId", "method: 'PUT'", "description: description.trim() || null", "image_asset_ids: imageAssetIds", "상품 변경 저장")),
    "Product Catalog UI can cancel a product edit": "onClick={clearProductForm}>편집 취소" in product_workspace,
    "Product Catalog UI binds multiple image assets": "image_asset_ids: imageAssetIds" in product_workspace and "multiple size={5}" in product_workspace,
    "Product Catalog UI discloses workspace SKU uniqueness": "Workspace 안에서 대소문자를 구분하지 않고 고유" in product_workspace,
    "Product Variant UI creates size/color options": all(value in product_workspace for value in ("/variants`,", "option_values", "variantColor", "variantSize")),
    "Product Variant UI selects variant-specific images": all(value in product_workspace for value in ("variantImageAssetIds", "image_asset_ids: variantImageAssetIds", "Variant 전용 이미지", "선택하지 않으면 상품 대표/갤러리 이미지")),
    "Product Variant UI updates existing variants with PUT": all(value in product_workspace for value in ("startVariantEdit", "editingVariantId", "method: 'PUT'", "Variant 변경 저장")),
    "Product Variant UI preserves additional option values on edit": "setVariantExtraOptions(Object.fromEntries(Object.entries(variant.option_values).filter" in product_workspace,
    "Product Variant UI adds and removes custom options with backend constraints": all(value in product_workspace for value in ("addExtraOption", "newOptionKey", "newOptionValue", "/^[a-z0-9_]{1,40}$/", "Object.keys(option_values).length > 12", "추가 옵션 키", "추가 옵션 값")),
    "Product Variant UI archives variants": "/variants/${encodeURIComponent(variantId)}/archive" in product_workspace,
    "Product Catalog clears stale edit forms after archive": all(value in product_workspace for value in ("if (editingProductId === productId) clearProductForm()", "if (variantParentId === productId) clearVariantForm()", "if (editingVariantId === variantId) clearVariantForm()")),
    "Product Variant UI rejects blank custom option values before API calls": "if (!value || value.length > 80)" in product_workspace,
    "Product Catalog aborts stale loads and guards workspace response races": all(value in product_workspace for value in ("new AbortController()", "return () => controller.abort()", "loadSequenceRef", "requestScopeRef.current.workspaceId !== workspaceId")),
    "Lookbook UI loads active Product catalog": "/v1/products?workspace_id=" in lookbook_workspace and "setProducts(productResult.items)" in lookbook_workspace,
    "Lookbook UI submits catalog Product references": "product_ids: productIds" in lookbook_workspace,
    "Lookbook UI selects active Product Variants": all(value in lookbook_workspace for value in ("product_variant_ids: productVariantIds", "product.variants", "variant.option_values")),
    "Lookbook UI submits for review and approves plans": all(value in lookbook_workspace for value in ("/${action}?workspace_id=", "reviewAction(draft.draft_id, 'approve')", "reviewAction(draft.draft_id, 'request-changes')")),
    "Lookbook UI exposes approved planning manifest": "/manifest?workspace_id=" in lookbook_workspace and "승인 기획 manifest 보기" in lookbook_workspace,
    "Lookbook UI discovers only individually approved Photo runs": all(value in lookbook_workspace for value in ("/v1/photo-drafts?workspace_id=", "review_status === 'approved'", "output_version_id")),
    "Lookbook UI attaches approved Photo outputs with Product Variant": all(value in lookbook_workspace for value in ("/outputs?workspace_id=", "photo_run_id: selectedPhotoRunId", "product_variant_id: selectedVariantId")),
    "Lookbook UI submits and reviews the assembled output sequence": all(value in lookbook_workspace for value in ("/outputs/submit?workspace_id=", "decideOutputAssembly('approve')", "decideOutputAssembly('reject')", "assemblyReview?.status === 'in_review'")),
    "Lookbook UI freezes output attachment once assembly review starts": "!assemblyEditable" in lookbook_workspace and "조립 순서를 별도로 검토·승인" in lookbook_workspace,
    "Lookbook UI exports only after assembly approval": all(value in lookbook_workspace for value in ("/outputs/manifest?workspace_id=", "승인된 Lookbook 결과 manifest 내보내기", "assemblyReview?.status !== 'approved'")),
    "Lookbook UI creates private binary package only after assembly approval": all(value in lookbook_workspace for value in ("/outputs/package-export?workspace_id=", "승인된 Lookbook 내부 ZIP 만들기", "Lookbook ZIP 다운로드", "packageExport.download_url", "assemblyReview?.status !== 'approved'")),
    "Lookbook UI labels private package as internal-only without rights grant": all(value in lookbook_workspace for value in ("내부 사용 전용", "게시 및 상업적 이용 권한은 부여되지 않습니다")),
    "Lookbook assembly owns and revokes authenticated preview object URLs": "AuthenticatedPreviewObjectUrls" in lookbook_workspace and "outputPreviewObjectUrlsRef.current.clear()" in lookbook_workspace,
    "Lookbook assembly displays exact immutable output version previews": all(value in lookbook_workspace for value in ("/versions/${encodeURIComponent(item.asset_version_id)}/preview-content", "outputPreviewUrls[item.output_item_id]", "exact AssetVersion preview")),
    "Lookbook assembly ignores stale draft-selection reads": all(value in lookbook_workspace for value in ("assemblyLoadRequestRef", "isAssemblyRequestCurrent", "requestId === assemblyLoadRequestRef.current")),
    "Lookbook manifest reads ignore older selections and workspace changes": all(value in lookbook_workspace for value in ("manifestRequestRef", "isManifestRequestCurrent", "manifestRequestRef.current += 1")),
    "Lookbook archive invalidates an active assembly for the archived draft": all(value in lookbook_workspace for value in ("if (assemblyDraftId === draftId) clearAssemblyState()", "manifestRequestRef.current += 1;", "setManifestJson(null);")),
    "Lookbook assembly reset clears all dependent selections, previews and exports": all(value in lookbook_workspace for value in ("const clearAssemblyState = useCallback", "setAssemblyDraftId(null)", "setApprovedPhotoRuns([])", "setAttachedOutputs([])", "setOutputPreviewUrls({})", "setSelectedPhotoRunId('')", "setSelectedVariantId('')", "setOutputManifestJson(null)", "setPackageExport(null)", "setAssemblyReview(null)")),
    "Lookbook assembly close uses the complete dependent-state reset": "onClick={clearAssemblyState}" in lookbook_workspace,
    "Lookbook UI explains separate assembly approval and metadata-only rights boundary": all(value in lookbook_workspace for value in ("조립 순서는 별도 검토·승인 후에만 내보낼 수 있습니다", "게시·상업 권리 승인은 실행되지 않습니다")),
}
checks.update(product_checks)
project_product_workspace = (root / "src/ProjectProductAssignmentWorkspace.tsx").read_text(encoding="utf-8")
project_product_checks = {
    "Project Product UI loads projects and catalog products": all(value in project_product_workspace for value in ("/v1/projects?workspace_id=", "/v1/products?workspace_id=")),
    "Project Product UI saves ordered assignments": "method: 'PUT'" in project_product_workspace and "product_ids: productIds" in project_product_workspace,
    "Project Product UI displays append-only assignment history": "/product-events`" in project_product_workspace and "event.details.reordered" in project_product_workspace,
    "Project Product UI aborts stale catalog and assignment reads": project_product_workspace.count("new AbortController()") >= 2 and project_product_workspace.count("controller.abort()") >= 2 and "return () => {" in project_product_workspace and "signal?.aborted" in project_product_workspace,
    "Project Product assignment reloads reject stale project selections": all(value in project_product_workspace for value in ("assignmentLoadSequenceRef", "selectedProjectRef.current !== selectedProjectId", "requestId !== assignmentLoadSequenceRef.current")),
    "Project Product catalog reloads reject older responses": "catalogLoadSequenceRef" in project_product_workspace and "requestId !== catalogLoadSequenceRef.current" in project_product_workspace,
    "Project selection invalidates prior assignment hydration and clears dependent state immediately": all(value in project_product_workspace for value in ("const selectProject = useCallback", "assignmentLoadSequenceRef.current += 1;\n    setProductIds([]);\n    setEvents([]);\n    setError(null);\n    setProjectId(nextProjectId);", "onChange={(event) => selectProject(event.currentTarget.value)}")),
    "Project assignment effect clears previous project's data before loading the next selection": all(value in project_product_workspace for value in ("Never display the previous project's assignments/history", "setProductIds([]);\n    setEvents([]);\n    setError(null);", "selectedProjectRef.current === projectId")),
    "Project catalog reconciliation invalidates assignments when the selected project disappears": all(value in project_product_workspace for value in ("if (nextProjectId !== selectedProjectRef.current)", "assignmentLoadSequenceRef.current += 1;\n      setProductIds([]);\n      setEvents([]);")),
}
checks.update(project_product_checks)

project_workspace = (root / "src/ProjectWorkspace.tsx").read_text(encoding="utf-8")
project_workspace_checks = {
    "Project Workspace creates and lists workspace-scoped projects": all(value in project_workspace for value in ("/v1/projects?workspace_id=", "method: 'POST'", "workspace_id: workspaceId")),
    "Project Workspace edits existing projects through PUT": all(value in project_workspace for value in ("editingProjectId", "method: 'PUT'", "project_type: projectType.trim()")),
    "Project Workspace supports non-destructive lifecycle states": all(value in project_workspace for value in ("'ACTIVE'", "'COMPLETED'", "'ARCHIVED'", "다시 활성화")),
    "Project Workspace explains active Lookbook reference guard": "활성 Lookbook 초안에서 사용 중인 프로젝트는 초안을 먼저 보관" in project_workspace,
    "Project Workspace keeps edit status synchronized after list lifecycle action": "if (editingProjectId === project.project_id) setStatus(nextStatus)" in project_workspace,
    "Project Workspace aborts stale loads and guards workspace response races": all(value in project_workspace for value in ("new AbortController()", "return () => controller.abort()", "loadSequenceRef", "requestScopeRef.current.workspaceId !== workspaceId")),
    "Project Workspace is exported from the viewer package": "ProjectWorkspace" in (root / "src/index.ts").read_text(encoding="utf-8"),
}
checks.update(project_workspace_checks)
output_review_workspace = (root / "src/OutputReviewWorkspace.tsx").read_text(encoding="utf-8")
output_review_checks = {
    "Output review UI reads persisted generation outputs and review history": "/outputs`" in output_review_workspace and "/review`" in output_review_workspace,
    "Output review UI previews the exact reviewed AssetVersion with authenticated fetch": "/versions/${encodeURIComponent(versionId)}/preview-content" in output_review_workspace and "immutable AssetVersion 미리보기" in output_review_workspace,
    "Output review UI supports approve, changes request and reject": all(value in output_review_workspace for value in ("'approve'", "'request-changes'", "'reject'")),
    "Output review UI exposes immutable AssetVersion and provenance": all(value in output_review_workspace for value in ("asset_version_id", "provenance_id", "checksum_sha256")),
    "Output review UI exports only the gated metadata manifest": "/outputs/export-manifest" in output_review_workspace and "publication_authorized" not in output_review_workspace,
    "Output review UI discloses publication and commercial-rights boundary": "공개 게시·상업적 이용 권리를 부여하지 않습니다" in output_review_workspace,
    "Output Review aborts stale job reads and nested previews": "new AbortController()" in output_review_workspace and "return () => controller.abort()" in output_review_workspace and "signal?.aborted" in output_review_workspace,
    "Output Review ignores out-of-order nested review and preview hydration": "loadSequenceRef" in output_review_workspace and output_review_workspace.count("requestId !== loadSequenceRef.current") >= 2 and "requestId === loadSequenceRef.current" in output_review_workspace,
    "Output Review decision and manifest mutations are serialized": all(value in output_review_workspace for value in ("reviewMutationInFlightRef.current", "if (reviewMutationInFlightRef.current) return", "setManifest(null)")),
    "Output Review scope reset releases mutation gate": "reviewMutationInFlightRef.current = false" in output_review_workspace,
    "Output review UI is exported from the viewer package": "OutputReviewWorkspace" in (root / "src/index.ts").read_text(encoding="utf-8"),
}
checks.update(output_review_checks)
checks["Output Review owns and revokes authenticated preview object URLs"] = "AuthenticatedPreviewObjectUrls" in output_review_workspace and "previewObjectUrlsRef.current.clear()" in output_review_workspace
# Mutation-in-flight scope protection and stale-scope state reset checks.
request_scope = (root / "src/useRequestScope.ts").read_text(encoding="utf-8")
checks.update({
    "Request scope helper delegates to the dependency-free lifecycle gate": all(value in request_scope for value in ("RequestScopeGate", "gateRef.current.update(key)", "gate?.dispose()", "gateRef.current!.isCurrent(captured)")),
    "Request scope gate implementation is included": (root / "src/requestScopeGate.mjs").is_file() and (root / "src/requestScopeGate.d.mts").is_file(),
    "Keyed request gate implementation and declarations are included": (root / "src/keyedRequestGate.mjs").is_file() and (root / "src/keyedRequestGate.d.mts").is_file(),
    "Request scope gate behavioral test covers scope, auth, API, unmount and remount": all(value in (root / "scripts/test_request_scope_gate.mjs").read_text(encoding="utf-8") for value in ("workspace change", "auth token change", "API origin change", "unmount", "reactivation")),
})
for component_name, component_source, mutation_markers in [
    ("Asset", workspace, ("restoreVersion", "upload", "removeAsset")),
    ("Photo Draft", photo_workspace, ("uploadImage", "createDraft", "runLocal", "reviewRun", "archiveDraft")),
    ("Lookbook", lookbook_workspace, ("createDraft", "reviewAction", "attachPhotoOutput", "submitOutputAssembly", "decideOutputAssembly", "createPackageExport", "archiveDraft")),
    ("Product Catalog", product_workspace, ("saveProduct", "archiveProduct", "saveVariant", "archiveVariant")),
    ("Project Product", project_product_workspace, ("const save = useCallback",)),
    ("Project", project_workspace, ("const save = useCallback", "statusAction")),
    ("Output Review", output_review_workspace, ("decide", "exportManifest")),
]:
    checks[f"{component_name} mutation callbacks capture and validate current request scope"] = (
        "captureScope" in component_source and "isScopeCurrent(scope)" in component_source
        and all(marker in component_source for marker in mutation_markers)
    )
for component_name, component_source in [
    ("Photo Draft", photo_workspace), ("Lookbook", lookbook_workspace),
    ("Product Catalog", product_workspace), ("Project Product", project_product_workspace),
    ("Project", project_workspace), ("Output Review", output_review_workspace),
]:
    checks[f"{component_name} clears prior-scope state on scope changes"] = "setBusy(false)" in component_source and "setError(null)" in component_source and "[base, accessToken," in component_source
checks["Asset and Photo loaders reject stale-scope follow-up reloads"] = all(value in workspace + photo_workspace for value in ("isScopeCurrent(scope)", "captureScope"))
checks["Lookbook and Output Review loaders reject stale-scope follow-up reloads"] = all(value in lookbook_workspace + output_review_workspace for value in ("isScopeCurrent(scope)", "captureScope"))

# Project lifecycle changes are broadcast to mounted dependent workspaces.
project_lifecycle_events = (root / "src/projectLifecycleEvents.mjs").read_text(encoding="utf-8")
checks.update({
    "Project lifecycle event helper scopes notifications by workspace and cleans up listeners": all(value in project_lifecycle_events for value in ("acs:project-lifecycle-changed", "workspaceId", "projectId", "addEventListener", "removeEventListener", "dispatchEvent")),
    "Project Workspace publishes lifecycle changes after successful project edits": "publishProjectLifecycleChange({ workspaceId, projectId: editingProjectId })" in project_workspace and "publishProjectLifecycleChange({ workspaceId, projectId: project.project_id })" in project_workspace,
    "Project Product Assignment refreshes active project catalog after lifecycle events": "subscribeProjectLifecycleChanges" in project_product_workspace and "change.workspaceId !== workspaceId" in project_product_workspace and "loadCatalog()" in project_product_workspace,
    "Project Product catalog ignores stale lifecycle refresh failures before parsing responses": project_product_workspace.index("requestId !== catalogLoadSequenceRef.current) return;") < project_product_workspace.index("if (!projectResponse.ok)"),
    "Lookbook refreshes project references after lifecycle events": "subscribeProjectLifecycleChanges" in lookbook_workspace and "change.workspaceId !== workspaceId" in lookbook_workspace and "load()" in lookbook_workspace,
    "Lookbook clears project selection when the project is no longer active": "setProjectId((current) => projectResult.items.some((project) => project.project_id === current) ? current : '')" in lookbook_workspace,
    "Lookbook lifecycle refreshes reject stale request errors and data": lookbook_workspace.index("requestId !== loadSequenceRef.current) return;") < lookbook_workspace.index("if (!response.ok)"),
})

# Immutable AssetVersion preview expiry/error recovery and retry protections.
checks.update({
    "Photo Draft previews track per-version authenticated fetch errors and loading": all(value in photo_workspace for value in ("previewErrors", "previewLoading", "preview-content", "response.blob()", "AssetVersion 미리보기를 불러오지 못했습니다.")),
    "Photo Draft preview failure clears the failed URL and offers explicit reissue retry": all(value in photo_workspace for value in ("handlePreviewImageError", "접근 권한이 없거나 이미지를 불러오지 못했습니다", "미리보기 / 재시도", "onError={(event) => handlePreviewImageError")),
    "Photo Draft preview retry remains bound to the exact immutable AssetVersion": all(value in photo_workspace for value in ("const previewKey = `${assetId}:${versionId}`", "encodeURIComponent(assetId)", "encodeURIComponent(versionId)", "previewRequestGateRef.current.isCurrent(previewKey, previewRequestId)")),
    "Output Review tracks per-output authenticated fetch errors and loading": all(value in output_review_workspace for value in ("previewErrors", "previewLoading", "preview-content", "previewResponse.blob()")),
    "Output Review supports explicit preview reissue and failed-image recovery": all(value in output_review_workspace for value in ("loadOutputPreview", "handlePreviewImageError", "미리보기 불러오기 / 재시도", "onError={(event) => handlePreviewImageError")),
    "Output Review preview retry is bound to the review's exact immutable AssetVersion": all(value in output_review_workspace for value in ("const assetId = review?.output.asset_id", "const versionId = review?.output.asset_version_id", "encodeURIComponent(assetId)", "encodeURIComponent(versionId)")),
    "Output Review latest preview hydration cannot overwrite a newer manual retry": all(value in output_review_workspace for value in ("previewRequestGateRef.current.next(output.id)", "previewRequestGateRef.current.isCurrent(id, previewRequestId)", "previewRequestGateRef.current.invalidateAll()")),
})
for label, passed in checks.items():
    print(f"{'PASS' if passed else 'FAIL'} {label}")
if not all(checks.values()):
    raise SystemExit(1)
print(f"{len(checks)} structural checks passed")
