/** Where the "Rebuilding stats is required" bar shows (pure; unit-tested). */
const BANNER_ROOTS = ['/reports', '/statistics', '/sessions', '/configuration'];

export function showsRebuildBanner(pathname: string, required: boolean, rebuilding: boolean): boolean {
  if (!required || rebuilding) return false;
  return BANNER_ROOTS.some((r) => pathname === r || pathname.startsWith(`${r}/`));
}
