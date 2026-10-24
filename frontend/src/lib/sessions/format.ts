/** Session list captions (sessions.md §3.3). Times are local naive ISO strings, never run through Date's timezone logic. */

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];
const WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

const ISO = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/;

export interface LocalStamp {
  year: number;
  month: number; // 1-12
  day: number;
  hour: number;
  minute: number;
}

export function parseLocal(iso: string): LocalStamp | null {
  const m = ISO.exec(iso);
  if (!m) return null;
  return { year: +m[1], month: +m[2], day: +m[3], hour: +m[4], minute: +m[5] };
}

const two = (n: number) => String(n).padStart(2, '0');

/** "20:10" */
export function clockHHMM(iso: string): string {
  const s = parseLocal(iso);
  return s ? `${two(s.hour)}:${two(s.minute)}` : '';
}

/**
 * Row / page-header caption: "October 17, Friday 20:10" (year prefixed when it is not `currentYear`),
 * or "17-10-2026, 20:10" in the numeric format.
 */
export function sessionCaption(iso: string, opts: { numeric: boolean; currentYear: number }): string {
  const s = parseLocal(iso);
  if (!s) return '';
  const clock = `${two(s.hour)}:${two(s.minute)}`;
  if (opts.numeric) return `${two(s.day)}-${two(s.month)}-${s.year}, ${clock}`;
  const weekday = WEEKDAYS[new Date(s.year, s.month - 1, s.day).getDay()];
  const year = s.year === opts.currentYear ? '' : `${s.year} `;
  return `${year}${MONTHS[s.month - 1]} ${s.day}, ${weekday} ${clock}`;
}

/** Live row text: "Live 14:05 - ..." */
export function liveCaption(iso: string): string {
  return `Live ${clockHHMM(iso)} - ...`;
}

/** Page-0 header text next to the LIVE pill: "14:05 - ..." */
export function liveClock(iso: string): string {
  return `${clockHHMM(iso)} - ...`;
}
