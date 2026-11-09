export interface ResourceRollbackError {
  name: string;
  message: string;
}
export interface ResourceRollbackResult {
  attemptedCount: number;
  completedCount: number;
  errors: ResourceRollbackError[];
}
export interface ResourceRollback {
  defer<T extends () => void>(name: string, dispose: T): T;
  release(dispose: () => void): boolean;
  commit(): boolean;
  rollback(onError?: (result: ResourceRollbackResult) => void): ResourceRollbackResult;
  readonly settled: boolean;
  readonly pendingCount: number;
}
export declare function createResourceRollback(): ResourceRollback;
