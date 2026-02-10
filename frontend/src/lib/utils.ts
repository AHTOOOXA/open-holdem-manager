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
