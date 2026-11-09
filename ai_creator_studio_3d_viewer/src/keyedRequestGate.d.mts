export class KeyedRequestGate {
  next(key: string): number;
  isCurrent(key: string, sequence: number): boolean;
  invalidate(key: string): void;
  invalidateAll(): void;
}
