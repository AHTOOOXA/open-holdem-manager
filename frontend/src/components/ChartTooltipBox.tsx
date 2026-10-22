import type { ReactNode } from 'react';
import { tooltipStyle } from '@/lib/chart-theme';

/** Shared popover box for Recharts custom tooltips. */
export function ChartTooltipBox({ children }: { children: ReactNode }) {
  return <div style={tooltipStyle}>{children}</div>;
}
