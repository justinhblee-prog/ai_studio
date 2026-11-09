/** Owns authenticated fetch-to-blob preview URLs and revokes replaced/unmounted entries. */
export class AuthenticatedPreviewObjectUrls {
  constructor(urlApi = URL) {
    this.urlApi = urlApi;
    this.urls = new Map();
  }

  replace(key, blob) {
    this.revoke(key);
    const url = this.urlApi.createObjectURL(blob);
    this.urls.set(key, url);
    return url;
  }

  revoke(key) {
    const current = this.urls.get(key);
    if (current) this.urlApi.revokeObjectURL(current);
    this.urls.delete(key);
  }

  clear() {
    for (const key of this.urls.keys()) this.revoke(key);
  }
}
