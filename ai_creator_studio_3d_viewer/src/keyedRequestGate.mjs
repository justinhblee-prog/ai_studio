/** Tracks the latest asynchronous request independently for each stable UI key. */
export class KeyedRequestGate {
  #sequences = new Map();

  next(key) {
    const sequence = (this.#sequences.get(key) || 0) + 1;
    this.#sequences.set(key, sequence);
    return sequence;
  }

  isCurrent(key, sequence) {
    return this.#sequences.get(key) === sequence;
  }

  invalidate(key) {
    this.#sequences.set(key, (this.#sequences.get(key) || 0) + 1);
  }

  invalidateAll() {
    for (const [key, sequence] of this.#sequences) this.#sequences.set(key, sequence + 1);
  }
}
