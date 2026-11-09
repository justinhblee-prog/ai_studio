export type AnimationFrameControllerOptions = {
  requestFrame: (callback: FrameRequestCallback) => number;
  cancelFrame: (frameId: number) => void;
  render: () => void;
  onError?: (error: unknown) => void;
};
export type AnimationFrameController = {
  start: () => boolean;
  stop: () => boolean;
  readonly running: boolean;
  readonly pendingFrameId: number | null;
};
export function createAnimationFrameController(options: AnimationFrameControllerOptions): AnimationFrameController;
