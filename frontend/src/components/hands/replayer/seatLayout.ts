/** Seat positioning math — places players around an ellipse with hero at bottom center. */

export interface SeatPosition {
  x: number;
  y: number;
}

/**
 * Returns {x, y} pixel coordinates for each seat around an elliptical table.
 * Seat 0 = hero (bottom center). Remaining seats distributed clockwise.
 */
export function getSeatPositions(
  playerCount: number,
  containerWidth: number,
  containerHeight: number,
): SeatPosition[] {
  const cx = containerWidth / 2;
  const cy = containerHeight / 2;
  // Ellipse radii — push seats closer to the edge of the container
  const rx = Math.max(0, containerWidth / 2 - 65);
  const ry = Math.max(0, containerHeight / 2 - 45);

  const positions: SeatPosition[] = [];

  for (let i = 0; i < playerCount; i++) {
    // Start from bottom (π/2) and go clockwise (subtract angle)
    const angle = Math.PI / 2 - (2 * Math.PI * i) / playerCount;
    const x = cx - rx * Math.cos(angle);
    const y = cy + ry * Math.sin(angle);
    positions.push({ x: Math.round(x), y: Math.round(y) });
  }

  return positions;
}

/**
 * Returns a position between the seat and the table center,
 * for rendering bet chips and action labels on the felt.
 */
export function getBetPosition(
  seat: SeatPosition,
  containerWidth: number,
  containerHeight: number,
): SeatPosition {
  const cx = containerWidth / 2;
  const cy = containerHeight / 2;
  // Side seats: less horizontal pull so bets stay toward sides
  const relX = Math.abs(seat.x - cx) / (containerWidth / 2);
  const tx = 0.45 - 0.15 * relX; // sides ~0.30, top/bottom ~0.45
  const ty = 0.45;
  return {
    x: Math.round(seat.x + (cx - seat.x) * tx),
    y: Math.round(seat.y + (cy - seat.y) * ty),
  };
}
