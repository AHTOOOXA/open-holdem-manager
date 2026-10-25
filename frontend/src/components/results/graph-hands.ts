import type { GraphPoint, GraphResponse } from '@/lib/api';

/** Number of hands in a graph response.
 *
 * The backend sends only the points the chart draws (about 1000, always including the last hand),
 * so `points.length` is not the hand count: use `hands`, else the last point's `hand_number`. */
export function graphHands(resp: { points: GraphPoint[]; hands?: GraphResponse['hands'] } | null | undefined): number {
  if (!resp) return 0;
  if (typeof resp.hands === 'number') return resp.hands;
  return lastHandNumber(resp.points);
}

/** Hand number of the last point (0 when there are none). */
export function lastHandNumber(points: readonly GraphPoint[]): number {
  return points.length ? points[points.length - 1].hand_number : 0;
}
