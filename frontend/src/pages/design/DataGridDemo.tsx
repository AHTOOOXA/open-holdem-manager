/**
 * DataGrid gallery demo (self-contained, fake data): sorting with desc-first numeric columns,
 * pinned summary row, money tones, sample-size dimming, column picker + resize (persisted under
 * "design-demo"), selection modes, density, sticky first column, a virtualised list with infinite
 * loading, and the empty / loading / error slots.
 */
import { useCallback, useState } from 'react';
import { DataGrid, createDataGridColumns, statCell, type GridSorting, type SelectionMode } from '@/components/ui/data-grid';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { count, signedUsd, trimmed } from '@/lib/format';

interface PlayerRow {
  id: string;
  name: string;
  hands: number;
  vpip: number;
  pfr: number;
  threeBet: number;
  threeBetOpp: number;
  bb100: number;
  won: number;
  ev: number;
}

/** Deterministic pseudo-random numbers so the demo looks the same on every load. */
function rng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

const NAMES = [
  'Hero', 'fishy_mcfish', 'GTO_wizard99', 'nitly', 'river_rat', 'cbet_machine', 'stack_or_bust',
  'limpy', 'callstation42', 'tight_tom', 'aggro_anna', 'button_bully', 'squeeze_play', 'donk_dan',
];

function makePlayers(): PlayerRow[] {
  const r = rng(7);
  return NAMES.map((name, i) => {
    const hands = Math.round(5 + r() * (i === 0 ? 20000 : 1800));
    const won = (r() - 0.45) * 400;
    const threeBetOpp = Math.round(hands * 0.08);
    return {
      id: `p${i}`,
      name,
      hands,
      vpip: 15 + r() * 40,
      pfr: 10 + r() * 22,
      threeBet: 2 + r() * 12,
      threeBetOpp,
      bb100: (won / Math.max(hands, 1)) * 100 * 20,
      won,
      ev: won + (r() - 0.5) * 60,
    };
  });
}

function totals(rows: PlayerRow[]): PlayerRow {
  const hands = rows.reduce((a, b) => a + b.hands, 0);
  const won = rows.reduce((a, b) => a + b.won, 0);
  const wavg = (k: 'vpip' | 'pfr' | 'threeBet') => rows.reduce((a, b) => a + b[k] * b.hands, 0) / Math.max(hands, 1);
  return {
    id: 'total',
    name: `Total (${rows.length})`,
    hands,
    vpip: wavg('vpip'),
    pfr: wavg('pfr'),
    threeBet: wavg('threeBet'),
    threeBetOpp: rows.reduce((a, b) => a + b.threeBetOpp, 0),
    bb100: (won / Math.max(hands, 1)) * 100 * 20,
    won,
    ev: rows.reduce((a, b) => a + b.ev, 0),
  };
}

const pc = createDataGridColumns<PlayerRow>();
const PLAYER_COLUMNS = pc.columns([
  pc.accessor('name', { header: 'Player', size: 150, meta: { title: 'Player name', minWidth: 90 } }),
  pc.accessor('hands', { header: 'Hands', size: 80, meta: { numeric: true }, cell: (i) => count(i.getValue()) }),
  pc.accessor('vpip', { header: 'VPIP', size: 64, meta: { numeric: true }, cell: statCell((r) => r.hands) }),
  pc.accessor('pfr', { header: 'PFR', size: 64, meta: { numeric: true }, cell: statCell((r) => r.hands) }),
  pc.accessor('threeBet', {
    header: '3Bet',
    size: 64,
    meta: { numeric: true, title: '3Bet preflop (sample = 3Bet opportunities)' },
    cell: statCell((r) => r.threeBetOpp),
  }),
  pc.accessor('bb100', {
    header: 'BB/100',
    size: 80,
    meta: { numeric: true, tone: 'money' },
    cell: (i) => trimmed(i.getValue(), 2),
  }),
  pc.accessor('won', {
    header: 'Won',
    size: 90,
    meta: { numeric: true, tone: 'money', className: 'font-medium' },
    cell: (i) => signedUsd(i.getValue()),
  }),
  pc.accessor('ev', {
    header: 'All-in adj',
    size: 96,
    meta: { numeric: true, tone: 'money', title: 'All-in EV adjusted winnings' },
    cell: (i) => signedUsd(i.getValue()),
  }),
]);

interface LogRow {
  id: string;
  n: number;
  hand: string;
  pot: number;
  result: number;
}

const lc = createDataGridColumns<LogRow>();
const LOG_COLUMNS = lc.columns([
  lc.accessor('n', { header: '#', size: 72, meta: { numeric: true, align: 'left' } }),
  lc.accessor('hand', { header: 'Hand id', size: 180, meta: { className: 'font-mono text-xs' } }),
  lc.accessor('pot', { header: 'Pot', size: 90, meta: { numeric: true }, cell: (i) => trimmed(i.getValue(), 1) }),
  lc.accessor('result', {
    header: 'Result',
    size: 100,
    meta: { numeric: true, tone: 'money' },
    cell: (i) => signedUsd(i.getValue()),
  }),
]);

function makeLog(from: number, n: number): LogRow[] {
  const r = rng(from + 1);
  return Array.from({ length: n }, (_, k) => {
    const i = from + k;
    return { id: `h${i}`, n: i + 1, hand: `RC${String(1_000_000_000 + i * 7919)}`, pot: r() * 120, result: (r() - 0.5) * 40 };
  });
}

const PAGE = 500;
const NO_PLAYERS: PlayerRow[] = [];
const PLAYERS = makePlayers();
const SUMMARY = totals(PLAYERS);
const playerId = (r: PlayerRow) => r.id;
const logId = (r: LogRow) => r.id;
const MAX_LOG = 5000;

function Label({ children }: { children: React.ReactNode }) {
  return <span className="text-label text-muted-foreground">{children}</span>;
}

export default function DataGridDemo() {
  const [sorting, setSorting] = useState<GridSorting>([{ id: 'hands', desc: true }]);
  const [density, setDensity] = useState<'default' | 'compact'>('default');
  const [selection, setSelection] = useState<SelectionMode>('single');
  const [selected, setSelected] = useState<string[]>([]);
  const [activated, setActivated] = useState<string | null>(null);

  const [log, setLog] = useState<LogRow[]>(() => makeLog(0, PAGE));
  const [loadingMore, setLoadingMore] = useState(false);
  const loadMore = useCallback(() => {
    if (log.length >= MAX_LOG) return;
    setLoadingMore(true);
    window.setTimeout(() => {
      setLog((l) => [...l, ...makeLog(l.length, PAGE)]);
      setLoadingMore(false);
    }, 400);
  }, [log.length]);

  const [stateDemo, setStateDemo] = useState<'empty' | 'loading' | 'error'>('loading');

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <Label>Density</Label>
            <ToggleGroup type="single" size="sm" variant="outline" value={density} onValueChange={(v) => v && setDensity(v as typeof density)}>
              <ToggleGroupItem value="default">Default</ToggleGroupItem>
              <ToggleGroupItem value="compact">Compact</ToggleGroupItem>
            </ToggleGroup>
          </div>
          <div className="flex items-center gap-2">
            <Label>Selection</Label>
            <ToggleGroup
              type="single"
              size="sm"
              variant="outline"
              value={selection}
              onValueChange={(v) => {
                if (!v) return;
                setSelection(v as SelectionMode);
                setSelected([]);
              }}
            >
              <ToggleGroupItem value="none">None</ToggleGroupItem>
              <ToggleGroupItem value="single">Single</ToggleGroupItem>
              <ToggleGroupItem value="multi">Multi</ToggleGroupItem>
            </ToggleGroup>
          </div>
          <span className="text-xs text-muted-foreground">
            {selected.length} selected{activated ? `, activated ${activated}` : ''}
          </span>
        </div>
        <DataGrid
          ariaLabel="Players"
          columns={PLAYER_COLUMNS}
          data={PLAYERS}
          getRowId={playerId}
          summary={SUMMARY}
          stickySummary
          density={density}
          sorting={sorting}
          onSortingChange={setSorting}
          selection={selection}
          selectedRowIds={selected}
          onSelectionChange={setSelected}
          onRowActivate={(r) => setActivated(r.name)}
          persistKey="design-demo"
          stickyFirstColumn
          maxHeight={320}
        />
        <p className="text-xs text-muted-foreground">
          Click a header (numbers sort high to low first), drag or arrow-key a header edge, gear menu for columns.
          Tab into the body: arrows, Home/End, PageUp/PageDown, Enter activates, Space selects.
        </p>
      </div>

      <div className="flex flex-col gap-2">
        <Label>
          Virtualised, compact, infinite loading ({count(log.length)} of {count(MAX_LOG)} rows, {PAGE} per load)
        </Label>
        <DataGrid
          ariaLabel="Hand log"
          columns={LOG_COLUMNS}
          data={log}
          getRowId={logId}
          density="compact"
          rowLines
          defaultSorting={[]}
          onEndReached={loadMore}
          loading={loadingMore}
          maxHeight={300}
        />
      </div>

      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <Label>States</Label>
          <ToggleGroup type="single" size="sm" variant="outline" value={stateDemo} onValueChange={(v) => v && setStateDemo(v as typeof stateDemo)}>
            <ToggleGroupItem value="loading">Loading</ToggleGroupItem>
            <ToggleGroupItem value="empty">Empty</ToggleGroupItem>
            <ToggleGroupItem value="error">Error</ToggleGroupItem>
          </ToggleGroup>
        </div>
        <DataGrid
          ariaLabel="State demo"
          columns={PLAYER_COLUMNS}
          data={NO_PLAYERS}
          getRowId={playerId}
          density="compact"
          columnPicker={false}
          loading={stateDemo === 'loading'}
          empty={stateDemo === 'empty' ? 'No players match these filters' : undefined}
          error={stateDemo === 'error' ? 'Failed to load players: backend offline' : undefined}
        />
      </div>
    </div>
  );
}
