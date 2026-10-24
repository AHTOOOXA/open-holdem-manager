/**
 * Left column of the Sessions screen: "Sessions (N)" header with Refresh and Switch Player, the
 * Date Range filter and the session list (DataGrid, newest first, Summary row last).
 */
import { useMemo } from 'react';
import { RefreshCw, UserRound } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { createDataGridColumns, DataGrid, type DataGridColumnDef } from '@/components/ui/data-grid';
import { DropdownMenuCheckboxItem } from '@/components/ui/dropdown-menu';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import SessionDateFilter from './SessionDateFilter';
import { count, duration, usd } from '@/lib/format';
import { liveCaption, sessionCaption } from '@/lib/sessions/format';
import type { StoredDateFilter } from '@/lib/sessions/date-filter';
import type { SessionRow, SessionsSummary } from '@/lib/sessions/types';
import { cn } from '@/lib/utils';

interface GridRow {
  key: string;
  start: string;
  isLive: boolean;
  duration: number;
  hands: number;
  won: number;
  wonEv: number;
  isSummary: boolean;
}

const SUMMARY_KEY = '__summary__';
const col = createDataGridColumns<GridRow>();
const rowId = (r: GridRow) => r.key;
const DEFAULT_SORTING = [{ id: 'session', desc: true }];
const GRID_MAX_HEIGHT = 'max(18rem, calc(100dvh - 16rem))';

function toGridRow(r: SessionRow): GridRow {
  return { key: String(r.id), start: r.start, isLive: r.is_live, duration: r.duration_s, hands: r.hands, won: r.won, wonEv: r.won_ev, isSummary: false };
}

function toSummaryRow(s: SessionsSummary): GridRow {
  return { key: SUMMARY_KEY, start: '', isLive: false, duration: s.duration_s, hands: s.hands, won: s.won, wonEv: s.won_ev, isSummary: true };
}

function buildColumns(numeric: boolean, currentYear: number): DataGridColumnDef<GridRow>[] {
  return col.columns([
    col.accessor('start', {
      id: 'session',
      header: 'Session Summary',
      size: 230,
      meta: { hideable: false, sortDescFirst: true },
      cell: ({ row }) => {
        const r = row.original;
        if (r.isSummary) return <span className="font-medium">Summary</span>;
        if (r.isLive) {
          return (
            <span className="inline-flex items-center gap-2">
              <span aria-hidden className="size-1.5 shrink-0 rounded-pill bg-destructive" />
              <span>{liveCaption(r.start)}</span>
            </span>
          );
        }
        return sessionCaption(r.start, { numeric, currentYear });
      },
    }),
    col.accessor('duration', { id: 'duration', header: 'Duration', size: 90, meta: { numeric: true }, cell: (i) => duration(i.getValue()) }),
    col.accessor('hands', { id: 'hands', header: 'Hands', size: 70, meta: { numeric: true }, cell: (i) => count(i.getValue()) }),
    col.accessor('won', { id: 'won', header: 'Won', size: 84, meta: { numeric: true, tone: 'money' }, cell: (i) => usd(i.getValue()) }),
    col.accessor('wonEv', { id: 'won_ev', header: 'Won EV', size: 84, meta: { numeric: true, tone: 'money', title: 'Won, all-in EV adjusted' }, cell: (i) => usd(i.getValue()) }),
  ]);
}

export interface SessionNavProps {
  rows: SessionRow[] | undefined;
  summary: SessionsSummary | null | undefined;
  loading: boolean;
  error: string | null;
  selectedId: number | null;
  onSelect: (id: number) => void;
  onRefresh: () => void;
  refreshing: boolean;
  playerName: string | null;
  onSwitchPlayer: () => void;
  dateFilter: StoredDateFilter;
  onDateFilter: (f: StoredDateFilter) => void;
  dayStartHour: number;
  numericDate: boolean;
  onNumericDate: (v: boolean) => void;
}

export default function SessionNav(p: SessionNavProps) {
  const currentYear = new Date().getFullYear();
  const columns = useMemo(() => buildColumns(p.numericDate, currentYear), [p.numericDate, currentYear]);
  const data = useMemo(() => (p.rows ?? []).map(toGridRow), [p.rows]);
  const summary = useMemo(() => (p.summary && data.length > 1 ? toSummaryRow(p.summary) : null), [p.summary, data.length]);
  const selectedIds = useMemo(() => (p.selectedId === null ? [] : [String(p.selectedId)]), [p.selectedId]);
  const { selectedId, onSelect } = p;
  const select = (ids: string[]) => {
    const id = Number(ids[0]);
    if (ids[0] && ids[0] !== SUMMARY_KEY && Number.isFinite(id) && id !== selectedId) onSelect(id);
  };

  return (
    <nav aria-label="Sessions" className="flex w-136 min-w-100 shrink-0 flex-col border-r border-border bg-card">
      <div className="flex items-center justify-between gap-2 py-3 pr-3 pl-6">
        <div className="flex items-center gap-1">
          <h2 className="text-lg font-normal">Sessions ({count(data.length)})</h2>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon-sm" aria-label="Refresh" onClick={p.onRefresh} className="text-muted-foreground">
                <RefreshCw className={cn(p.refreshing && 'animate-spin')} aria-hidden />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Refresh</TooltipContent>
          </Tooltip>
        </div>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="outline" size="sm" onClick={p.onSwitchPlayer} aria-label="Switch Player" className="max-w-52">
              <UserRound aria-hidden />
              <span className="truncate">{p.playerName ?? 'Switch Player'}</span>
            </Button>
          </TooltipTrigger>
          <TooltipContent>Switch Player</TooltipContent>
        </Tooltip>
      </div>
      <div className="flex items-center gap-3 bg-surface-sunken px-6 py-2">
        <span className="text-sm text-muted-foreground">Date Range</span>
        <SessionDateFilter value={p.dateFilter} onChange={p.onDateFilter} dayStartHour={p.dayStartHour} />
      </div>
      <DataGrid
        ariaLabel="Sessions"
        columns={columns}
        data={data}
        getRowId={rowId}
        summary={summary}
        stickySummary
        density="default"
        selection="single"
        selectedRowIds={selectedIds}
        onSelectionChange={select}
        defaultSorting={DEFAULT_SORTING}
        persistKey="sessions.list"
        loading={p.loading}
        error={p.error ? <span className="text-sm text-muted-foreground">Couldn't load sessions. {p.error}</span> : undefined}
        empty="No results yet"
        maxHeight={GRID_MAX_HEIGHT}
        columnPickerExtra={(
          <DropdownMenuCheckboxItem
            checked={p.numericDate}
            onCheckedChange={(v) => p.onNumericDate(v === true)}
            onSelect={(e) => e.preventDefault()}
          >
            Numeric Date Format
          </DropdownMenuCheckboxItem>
        )}
        className="w-full"
      />
    </nav>
  );
}
