from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
viewer = (ROOT / 'src/Studio3DViewer.tsx').read_text()
helper = (ROOT / 'src/boundedModelDownload.mjs').read_text()

checks = {
    'bounded download constant is explicit': 'MAX_MODEL_DOWNLOAD_BYTES = 256 * 1024 * 1024' in helper,
    'declared content length rejected before streaming': 'parsedLength > BigInt(MAX_MODEL_DOWNLOAD_BYTES)' in helper and 'cancelResponseBody(response' in helper,
    'streaming reader used instead of unbounded arrayBuffer': 'response.body.getReader()' in helper and 'response.arrayBuffer()' not in viewer + helper,
    'actual streamed bytes counted': 'const nextTotal = total + value.byteLength' in helper and 'total = nextTotal' in helper,
    'stream cap enforced during transfer': 'if (nextTotal > MAX_MODEL_DOWNLOAD_BYTES)' in helper and 'nextTotal > declaredLength' in helper,
    'unknown-length responses use capped geometric buffer growth': 'currentCapacity * 2' in helper and 'MAX_MODEL_DOWNLOAD_BYTES' in helper and 'unknownLengthBuffer' in helper,
    'known and unknown allocation failures map to typed memory error': helper.count("ModelDownloadError('memory'") >= 3 and 'Insufficient memory for model download.' in helper,
    'known-length allocation occurs before stream lock': helper.index('knownLengthBuffer = new Uint8Array(declaredLength)') < helper.index('const reader = response.body.getReader()'),
    'unknown-length buffer reuses exact-capacity backing store': 'total === unknownLengthBuffer.byteLength' in helper,
    'reader cancelled on oversize': "reader.cancel('Model exceeds the client download limit.')" in helper and "cancelResponseBody(response, 'Model exceeds the client download limit.')" in helper,
    'abort checked during and after streaming': helper.count('signal?.aborted') >= 3,
    '401 has authentication recovery guidance': "case 'unauthorized': return '로그인이 만료되었습니다." in viewer,
    '403 has authorization recovery guidance': "case 'forbidden': return '이 모델을 볼 권한이 없습니다." in viewer,
    '404 has missing-version recovery guidance': "case 'not_found': return '요청한 모델 버전을 찾을 수 없습니다." in viewer,
    '409 has stale-version recovery guidance': "case 'conflict': return '모델 버전 상태가 변경되었습니다." in viewer,
    'oversize has explicit UI guidance': "case 'too_large': return '모델 파일이 현재 뷰어의 다운로드 한도(256 MiB)를 초과합니다.'" in viewer,
    'error state displays actionable message': '<span>{errorMessage}</span>' in viewer,
    'raw response body and URL are not surfaced': 'response.status})' not in viewer and 'onErrorRef.current?.(modelUrl)' not in viewer,
    'authenticated no-store fetch retained': "cache: 'no-store'" in viewer and 'Authorization: `Bearer ${accessToken}`' in viewer and 'readModelResponse(response' in viewer,
}
failed = [name for name, passed in checks.items() if not passed]
for name, passed in checks.items():
    print(f"{'PASS' if passed else 'FAIL'} {name}")
if failed:
    raise SystemExit(f'{len(failed)} checks failed: {failed}')
print(f'Bounded GLTF download and recovery: {len(checks)}/{len(checks)} PASS')
