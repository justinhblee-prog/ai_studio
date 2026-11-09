import { useCallback, useEffect, useRef } from 'react';
import { RequestScopeGate } from './requestScopeGate.mjs';

/** Prevents async UI work from an obsolete API/auth/workspace/job scope from mutating current state. */
export function useRequestScope(scopeParts: readonly (string | null | undefined)[]) {
  const key = JSON.stringify(scopeParts);
  const gateRef = useRef<RequestScopeGate | null>(null);
  if (!gateRef.current) gateRef.current = new RequestScopeGate(key);
  gateRef.current.update(key);

  useEffect(() => {
    const gate = gateRef.current;
    gate?.activate();
    return () => gate?.dispose();
  }, [key]);

  const capture = useCallback(() => gateRef.current!.capture(), []);
  const isCurrent = useCallback((captured: string) => gateRef.current!.isCurrent(captured), []);
  return { capture, isCurrent };
}
