export class AuthenticatedPreviewObjectUrls {
  constructor(urlApi?: Pick<typeof URL, 'createObjectURL' | 'revokeObjectURL'>);
  replace(key: string, blob: Blob): string;
  revoke(key: string): void;
  clear(): void;
}
