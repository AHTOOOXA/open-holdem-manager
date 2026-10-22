/** Date/time formatters shared by pages. Output strings are stable; tests pin them. */

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

/** Local 24h "HH:MM" of a Date. */
export function formatHHMM(d: Date): string {
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

/** ISO string -> "14:05" (24h, local). Empty string for empty input. */
export function formatClockTime(iso: string): string {
  if (!iso) return '';
  return new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
}

/** ISO string -> "Mon, Jan 5, 2026". Empty string for empty input. */
export function formatSessionDate(iso: string): string {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

/** ISO string -> "Jan 5, 2026 14:05". Empty string for empty input. */
export function formatDateTime(iso: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  return (
    d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) +
    ' ' +
    formatClockTime(iso)
  );
}

/** ISO string -> "Jan 5, 2026"; null/empty -> em dash. */
export function formatMediumDate(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

/** Checkpoint timestamp: "Jan 5" when at midnight, else "Jan 5 14:05". */
export function formatCheckpointDateTime(iso: string): string {
  const d = new Date(iso);
  const date = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  const time = formatHHMM(d);
  return time !== '00:00' ? `${date} ${time}` : date;
}
