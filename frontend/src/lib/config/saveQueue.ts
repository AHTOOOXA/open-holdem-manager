/**
 * Serialised saves, latest wins: at most one request in flight; while it runs, newer values replace
 * each other and only the last is sent afterwards. Pure (no React), unit-tested.
 */
export interface SaveQueueHandlers<T, R> {
  send: (value: T) => Promise<R>;
  /** A request succeeded. `more` is true when a newer value is queued (do not overwrite the cache with `result`). */
  onSaved: (result: R, more: boolean) => void;
  /** A request failed; the queue is dropped (the caller rolls back to the last server value). */
  onFailed: (error: Error) => void;
}

export function createSaveQueue<T, R>(h: SaveQueueHandlers<T, R>) {
  let inFlight = false;
  let pending: { value: T } | null = null;

  async function drain(): Promise<void> {
    inFlight = true;
    try {
      while (pending) {
        const { value } = pending;
        pending = null;
        try {
          const result = await h.send(value);
          h.onSaved(result, pending !== null);
        } catch (e) {
          pending = null;
          h.onFailed(e instanceof Error ? e : new Error(String(e)));
        }
      }
    } finally {
      inFlight = false;
    }
  }

  return {
    /** True while nothing is in flight or queued (the cache then equals the server). */
    idle: () => !inFlight && pending === null,
    push(value: T): void {
      pending = { value };
      if (!inFlight) void drain();
    },
  };
}
