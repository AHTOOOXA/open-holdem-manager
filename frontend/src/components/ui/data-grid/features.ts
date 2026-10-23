/**
 * TanStack Table v9 feature registry and column types shared by every DataGrid.
 * Build columns with `createDataGridColumns<Row>()` so `meta` is typed as DataGridColumnMeta.
 */
import {
  columnResizingFeature,
  columnSizingFeature,
  columnVisibilityFeature,
  createColumnHelper,
  createSortedRowModel,
  metaHelper,
  rowSortingFeature,
  sortFn_alphanumeric,
  sortFn_basic,
  sortFn_datetime,
  sortFn_text,
  tableFeatures,
  type ColumnDef,
  type RowData,
} from '@tanstack/react-table';

export interface DataGridColumnMeta {
  /** Cell and header alignment. Default: 'right' for numeric columns, else 'left'. */
  align?: 'left' | 'right' | 'center';
  /** Numeric column: right-aligned, sorts descending first. */
  numeric?: boolean;
  /** Full caption: header tooltip and column picker label (defaults to the string header). */
  title?: string;
  /** 'money': tone the cell with moneyClass(value) (value must be a number). */
  tone?: 'money';
  /** Decimals the money value is shown with (zero rule of moneyClass). Default 2. */
  moneyDigits?: number;
  /** May the user hide it in the column picker. Default true; the first column never can. */
  hideable?: boolean;
  /** First click sorts descending. Default: `numeric`. */
  sortDescFirst?: boolean;
  /** Minimum width in px while resizing (TanStack `minSize` wins when both are set). */
  minWidth?: number;
  /** Extra classes on body and summary cells. */
  className?: string;
  /** Extra classes on the header cell. */
  headerClassName?: string;
}

export const dataGridFeatures = tableFeatures({
  rowSortingFeature,
  sortedRowModel: createSortedRowModel(),
  sortFns: {
    alphanumeric: sortFn_alphanumeric,
    basic: sortFn_basic,
    datetime: sortFn_datetime,
    text: sortFn_text,
  },
  columnVisibilityFeature,
  columnSizingFeature,
  columnResizingFeature,
  columnMeta: metaHelper<DataGridColumnMeta>(),
});

export type DataGridFeatures = typeof dataGridFeatures;

/** A DataGrid column definition (TanStack v9 ColumnDef over the grid's features). */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type DataGridColumnDef<T extends RowData> = ColumnDef<DataGridFeatures, T, any>;

/** Typed column helper: `const col = createDataGridColumns<Row>(); col.accessor('won', {...})`. */
export function createDataGridColumns<T extends RowData>() {
  return createColumnHelper<DataGridFeatures, T>();
}
