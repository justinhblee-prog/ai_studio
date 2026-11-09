from pathlib import Path

source = Path(__file__).resolve().parents[1] / "src" / "LookbookDraftWorkspace.tsx"
text = source.read_text(encoding="utf-8")
checks = {
    "exact immutable AssetVersion preview endpoint": "/v1/assets/${encodeURIComponent(item.asset_id)}/versions/${encodeURIComponent(item.asset_version_id)}/preview-content" in text,
    "authenticated object URL lifecycle": "outputPreviewObjectUrlsRef.current.replace(outputId, previewBlob)" in text and "outputPreviewObjectUrlsRef.current.clear()" in text,
    "per-output preview status": "Record<string, OutputPreviewState>" in text,
    "per-output request sequencing": "outputPreviewRequestGateRef.current.next(outputId)" in text,
    "latest request guard": "outputPreviewRequestGateRef.current.isCurrent(outputId, requestId)" in text,
    "scope guard": "&& isScopeCurrent(scope)" in text,
    "prior preview URL cleared before retry": "outputPreviewUrlRef.current[outputId] = '';" in text,
    "stale image error guard": "isCurrentPreviewUrl(outputPreviewUrlRef.current[item.output_item_id], failedUrl)" in text,
    "manual preview recovery action": "미리보기 새로고침 / 재시도" in text,
    "signed download expiry parsed": "getSignedDownloadExpiry(packageExport.download_url, base)" in text,
    "signed download expiry preflight": "if (!isSignedLinkUsable(signedExpiry))" in text,
    "download uses no-store fetch": "fetch(packageExport.download_url, { method: 'GET', headers, cache: 'no-store' })" in text,
    "download uses blob": "URL.createObjectURL(blob)" in text,
    "package reissue action": "새 ZIP 및 다운로드 링크 발급" in text,
    "signed URL expiry distinguished from package retention": "다운로드 서명 링크 만료" in text and "보관 만료" in text,
    "export history fetched with assembly": "/outputs/exports?workspace_id=" in text,
    "export history retained in workspace state": "packageExportHistory" in text,
    "export history shows immutable snapshot hash": "Snapshot SHA-256 {entry.snapshot_sha256}" in text,
    "export history distinguishes missing files": "'파일 없음'" in text and "entry.status === 'expired'" in text,
}
for label, passed in checks.items():
    print(("PASS " if passed else "FAIL ") + label)
failed = [label for label, passed in checks.items() if not passed]
print(f"Lookbook preview recovery structural checks: {len(checks) - len(failed)}/{len(checks)} PASS")
if failed:
    raise SystemExit(1)
