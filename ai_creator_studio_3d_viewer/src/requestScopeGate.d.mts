export declare class RequestScopeGate {
  constructor(key: string);
  update(key: string): void;
  capture(): string;
  isCurrent(token: string): boolean;
  activate(): void;
  dispose(): void;
}
