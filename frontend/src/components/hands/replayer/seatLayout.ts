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
  // Ellipse radii — inset enough that ~110px-wide seats stay inside container
  const rx = Math.max(0, containerWidth / 2 - 65);
  const ry = Math.max(0, containerHeight / 2 - 50);

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
