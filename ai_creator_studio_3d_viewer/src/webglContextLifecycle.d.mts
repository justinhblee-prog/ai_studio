export type WebGLContextLifecycleOptions = {
  canvas: {
    addEventListener(type: string, listener: (event: Event) => void, options?: boolean): void;
    removeEventListener(type: string, listener: (event: Event) => void, options?: boolean): void;
  };
  animationLoop: { start(): unknown; stop(): unknown; readonly running?: boolean };
  clock?: { start?: () => unknown; stop?: () => unknown } | null;
  resize?: () => void;
  onLost?: (event?: Event) => void;
  onRestored?: (event?: Event) => void;
  onError?: (error: unknown) => void;
};

export function attachWebGLContextLifecycle(options: WebGLContextLifecycleOptions): {
  dispose(): boolean;
  readonly lost: boolean;
  readonly disposed: boolean;
};

/** Bounded retry for transient listener-removal failures during viewer teardown. */
export function disposeWebGLContextLifecycleWithRetry(
  lifecycle: { dispose(): boolean; readonly disposed?: boolean },
  maxAttempts?: number,
): boolean;
