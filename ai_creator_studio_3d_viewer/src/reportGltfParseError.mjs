/** Apply a GLTF parse failure only while its owning request is still active. */
export function reportGltfParseError({ cancelled, message, setErrorMessage, setLoadState, notifyError }) {
  if (cancelled) return false;
  setErrorMessage(message);
  setLoadState('error');
  notifyError?.(message);
  return true;
}
