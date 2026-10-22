/**
 * Chart styling as CSS-variable references (tokens live in src/index.css).
 * Recharts accepts `var(--x)` for stroke / fill, so charts follow the theme.
 */
import type { CSSProperties } from 'react';

export const chartColors = {
  main: 'var(--chart-main)',
  ev: 'var(--chart-ev)',
  showdown: 'var(--chart-sd)',
  nonshowdown: 'var(--chart-nsd)',
  rake: 'var(--chart-rake)',
  ci: 'var(--chart-main)',
  session: 'var(--muted-foreground)',
  axis: 'var(--chart-axis)',
  grid: 'var(--chart-grid)',
  /** Zero line: axis colour at half strength. */
  zeroLine: 'color-mix(in oklch, var(--chart-axis) 50%, transparent)',
  tooltipBg: 'var(--popover)',
  tooltipBorder: 'var(--border)',
  tooltipText: 'var(--foreground)',
  tooltipMuted: 'var(--muted-foreground)',
} as const;

export function axisTick(fontSize = 11) {
  return { fontSize, fill: chartColors.axis };
}

export const tooltipStyle: CSSProperties = {
  backgroundColor: chartColors.tooltipBg,
  border: `1px solid ${chartColors.tooltipBorder}`,
  borderRadius: '8px',
  color: chartColors.tooltipText,
  padding: '8px 12px',
  fontSize: '13px',
};

/** Frequency heatmap fill: the primary colour at `alphaPct` percent opacity. */
export function heat(alphaPct: number): string {
  return `color-mix(in oklch, var(--primary) ${alphaPct}%, transparent)`;
}

/** Win/loss heatmap fill: green for positive, red for negative, alpha 20-65%. */
export function moneyHeat(value: number, max: number): string {
  if (value === 0) return 'color-mix(in oklch, var(--foreground) 3%, transparent)';
  const clamp = max > 0 ? Math.min(Math.abs(value) / max, 1) : 0;
  const alphaPct = Math.round((clamp * 0.45 + 0.2) * 100);
  const base = value > 0 ? 'var(--money-pos)' : 'var(--money-neg)';
  return `color-mix(in oklch, ${base} ${alphaPct}%, transparent)`;
}
