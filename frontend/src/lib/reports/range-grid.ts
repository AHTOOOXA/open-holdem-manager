/** 13x13 preflop range grid helpers: pairs on the diagonal, suited upper-right, offsuit lower-left. */

export const RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'] as const;
export const GRID_SIZE = RANKS.length;

export interface GridPos {
  row: number;
  col: number;
}

/** Hand class at a grid position: (0,0) "AA", (0,1) "AKs", (1,0) "AKo". */
export function classAt(row: number, col: number): string {
  const r1 = RANKS[row];
  const r2 = RANKS[col];
  if (row === col) return r1 + r2;
  if (col > row) return r1 + r2 + 's';
  return r2 + r1 + 'o';
}

/** Grid position of a hand class ("AKs" -> row 0, col 1); null for anything that is not a class. */
export function posOfClass(cls: string): GridPos | null {
  const a = RANKS.indexOf(cls[0] as (typeof RANKS)[number]);
  const b = RANKS.indexOf(cls[1] as (typeof RANKS)[number]);
  if (a < 0 || b < 0) return null;
  if (a === b) return cls.length === 2 ? { row: a, col: a } : null;
  if (cls[2] === 's') return { row: Math.min(a, b), col: Math.max(a, b) };
  if (cls[2] === 'o') return { row: Math.max(a, b), col: Math.min(a, b) };
  return null;
}

/** All classes in the rectangle spanned by two corner positions (any corner order), row-major. */
export function rectClasses(a: GridPos, b: GridPos): string[] {
  const r0 = Math.min(a.row, b.row);
  const r1 = Math.max(a.row, b.row);
  const c0 = Math.min(a.col, b.col);
  const c1 = Math.max(a.col, b.col);
  const out: string[] = [];
  for (let r = r0; r <= r1; r++) for (let c = c0; c <= c1; c++) out.push(classAt(r, c));
  return out;
}

/** Selection with `cls` toggled; keeps the grid's row-major order. */
export function toggleClass(selected: readonly string[], cls: string): string[] {
  return selected.includes(cls) ? selected.filter((c) => c !== cls) : sortClasses([...selected, cls]);
}

/** Union of two selections in grid order. */
export function unionClasses(a: readonly string[], b: readonly string[]): string[] {
  return sortClasses([...new Set([...a, ...b])]);
}

function sortClasses(list: string[]): string[] {
  const idx = (c: string) => {
    const p = posOfClass(c);
    return p ? p.row * GRID_SIZE + p.col : Infinity;
  };
  return list.sort((x, y) => idx(x) - idx(y));
}

/** Move a focus position by an arrow key, clamped to the grid. */
export function moveFocus(pos: GridPos, key: string): GridPos {
  const clamp = (n: number) => Math.max(0, Math.min(GRID_SIZE - 1, n));
  switch (key) {
    case 'ArrowUp':
      return { row: clamp(pos.row - 1), col: pos.col };
    case 'ArrowDown':
      return { row: clamp(pos.row + 1), col: pos.col };
    case 'ArrowLeft':
      return { row: pos.row, col: clamp(pos.col - 1) };
    case 'ArrowRight':
      return { row: pos.row, col: clamp(pos.col + 1) };
    default:
      return pos;
  }
}
