/**
 * Format a Date as 'YYYY-MM-DD' in the user's local timezone.
 *
 * Don't use `toISOString().slice(0, 10)` for this: it converts to UTC first,
 * so east of UTC it returns yesterday's date shortly after midnight.
 */
export function formatLocalDate(d: Date = new Date()): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}
