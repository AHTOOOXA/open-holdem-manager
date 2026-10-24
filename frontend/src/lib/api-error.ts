/** Error helpers shared by the typed API clients. */

/** `what: detail` from a FastAPI error body (`{detail: string}`), else `what: status statusText`. */
export async function responseError(res: Response, what: string): Promise<Error> {
  try {
    const body = await res.json();
    if (body && typeof body.detail === 'string') return new Error(`${what}: ${body.detail}`);
  } catch {
    // not JSON
  }
  return new Error(`${what}: ${res.status} ${res.statusText}`);
}

/** The backend answered 404 "Player not found" (a stored player id that is gone from this database). */
export function isPlayerNotFound(e: unknown): boolean {
  return e instanceof Error && /player not found/i.test(e.message);
}

export const PLAYER_GONE_MESSAGE = 'That player is no longer in this database';
