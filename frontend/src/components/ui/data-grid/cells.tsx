import type { CellContext, RowData } from '@tanstack/react-table';
import { StatValue, type StatValueFormat } from '@/components/ui/stat-value';
import type { DataGridFeatures } from './features';

/**
 * Cell renderer for stat columns: the value with the one sample-size rule (dimmed low samples,
 * trailing sample count) via <StatValue>. `sample` reads the opportunities behind the value.
 *
 *   col.accessor('vpip', { header: 'VPIP', meta: { numeric: true }, cell: statCell((r) => r.hands) })
 */
export function statCell<T extends RowData>(sample: (row: T) => number | null | undefined, format: StatValueFormat = 'pct') {
  return function StatCell(info: CellContext<DataGridFeatures, T, unknown>) {
    const v = info.getValue();
    return <StatValue value={typeof v === 'number' ? v : null} sample={sample(info.row.original)} format={format} />;
  };
}
