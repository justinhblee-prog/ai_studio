export interface ViewerCleanupError { name: string; message: string }
export interface ViewerCleanupResult { attemptedCount: number; completedCount: number; errors: ViewerCleanupError[] }
export declare function runViewerCleanupSteps(steps: Array<{ name?: string; run: () => unknown }>, onError?: (result: ViewerCleanupResult) => void): ViewerCleanupResult;
