/** Small dependency-free gate for invalidating async UI work across scope changes/unmounts. */
export class RequestScopeGate {
  #key;
  #generation = 0;
  #mounted = true;

  constructor(key) {
    this.#key = key;
  }

  update(key) {
    if (key !== this.#key) {
      this.#key = key;
      this.#generation += 1;
    }
  }

  capture() {
    return JSON.stringify([this.#key, this.#generation]);
  }

  isCurrent(token) {
    return this.#mounted && token === this.capture();
  }

  activate() {
    this.#mounted = true;
  }

  dispose() {
    this.#mounted = false;
    this.#generation += 1;
  }
}
