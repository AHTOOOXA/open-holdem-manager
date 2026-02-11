import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Convert a stakes string like "$0.05/$0.10" to "NL10" notation.
 * Falls back to the original string if parsing fails.
 */
export function formatStakes(stakes: string): string {
  const m = stakes.match(/\$?([\d.]+)\/\$?([\d.]+)/);
  if (!m) return stakes;
  const bb = parseFloat(m[2]);
  if (isNaN(bb) || bb <= 0) return stakes;
  return `NL${Math.round(bb * 100)}`;
}

/**
 * Format an ISO date string as a relative date ("5m ago", "3h ago")
 * or short date ("Jan 15", "Dec 3 '24").
 */
export function formatRelativeDate(iso: string): string {
  const now = new Date();
  const d = new Date(iso);
  const diffMs = now.getTime() - d.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;

  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const sameYear = d.getFullYear() === now.getFullYear();
  if (sameYear) {
    return `${months[d.getMonth()]} ${d.getDate()}`;
  }
  return `${months[d.getMonth()]} ${d.getDate()} '${String(d.getFullYear()).slice(-2)}`;
}
