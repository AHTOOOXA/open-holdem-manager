import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getCashDropStats } from '@/lib/api';
import type { CashDropRangeCategory, ComboStats } from '@/lib/api';
import { useFilterOptions } from '@/hooks/useFilterOptions';
import { queryKeys } from '@/lib/query-keys';
import FilterBar from '@/components/FilterBar';
import EmptyState from '@/components/EmptyState';
import { Card, CardContent } from '@/components/ui/card';

// ── Heatmap helpers ──────────────────────────────────────────────────

const RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'];

function comboKey(row: number, col: number): string {
  const r1 = RANKS[row];
  const r2 = RANKS[col];
  if (row === col) return r1 + r2;
  if (col > row) return r1 + r2 + 's';
  return r2 + r1 + 'o';
}

function getCellColor(hands: number, maxHands: number): string {
  if (hands === 0) return 'transparent';
  const intensity = maxHands > 0 ? Math.min(hands / maxHands, 1) : 0;
  const alpha = Math.round(intensity * 45 + 8);
  return `rgba(99, 102, 241, ${alpha / 100})`;
}

// ── Field Heatmap ────────────────────────────────────────────────────

function FieldHeatmap({ category }: { category: CashDropRangeCategory }) {
  const [hovered, setHovered] = useState<string | null>(null);

  const comboMap = useMemo(() => {
    const m = new Map<string, ComboStats>();
    for (const c of category.combos) m.set(c.combo, c);
    return m;
  }, [category]);

  const maxHands = useMemo(() => {
    let max = 0;
    for (const c of category.combos) max = Math.max(max, c.hands);
    return max || 1;
  }, [category]);

  const hoveredCombo = hovered ? comboMap.get(hovered) : null;

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium">{category.label}</h3>
        <span className="text-xs text-text-muted">{category.total_hands} hands</span>
      </div>
      <div
        className="grid gap-[1px]"
        style={{ gridTemplateColumns: `repeat(13, 1fr)` }}
      >
        {RANKS.map((_, row) =>
          RANKS.map((_, col) => {
            const key = comboKey(row, col);
            const combo = comboMap.get(key);
            const hands = combo?.hands ?? 0;
            const bg = getCellColor(hands, maxHands);
            const isSuited = col > row;
            const isPair = col === row;
            const isHovered = hovered === key;

            return (
              <div
                key={`${row}-${col}`}
                className={`flex flex-col items-center justify-center ${isHovered ? 'ring-1 ring-primary z-10' : ''}`}
                style={{
                  backgroundColor: bg,
                  aspectRatio: '1',
                  border: '1px solid oklch(1 0 0 / 10%)',
                }}
                onMouseEnter={() => setHovered(key)}
                onMouseLeave={() => setHovered(null)}
              >
                <span className={`text-[7px] font-mono leading-none ${
                  hands > 0
                    ? isSuited ? 'text-primary' : isPair ? 'text-yellow' : 'text-text'
                    : 'text-text-muted/40'
                }`}>
                  {key}
                </span>
                {hands > 0 && (
                  <span className="text-[7px] font-mono text-text-muted leading-none mt-px">
                    {hands}
                  </span>
                )}
              </div>
            );
          })
        )}
      </div>
      {hoveredCombo && (
        <div className="mt-2 text-xs text-text-muted font-mono">
          {hovered}: {hoveredCombo.hands} hands
        </div>
      )}
    </Card>
  );
}

// ── Main Component ───────────────────────────────────────────────────

export default function CashDropPage() {
  const [stakes, setStakes] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  // Shared filter options
  const { data: filterOpts } = useFilterOptions();

  // Cash drop data query
  const cashDropParams = useMemo(() => ({
    stakes: stakes || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  }), [stakes, dateFrom, dateTo]);

  const { data, isPending: loading } = useQuery({
    queryKey: queryKeys.cashDrop(cashDropParams),
    queryFn: () => getCashDropStats(cashDropParams),
  });

  const s = data?.summary;

  const hasFilters = !!(stakes || dateFrom || dateTo);

  return (
    <div className="max-w-[1400px] mx-auto space-y-2">
      {/* Filter Bar */}
      <FilterBar
        stakes={stakes}
        onStakesChange={setStakes}
        showGameMode={false}
        dateFrom={dateFrom}
        onDateFromChange={setDateFrom}
        dateTo={dateTo}
        onDateToChange={setDateTo}
        showDatePresets={false}
        filterOptions={filterOpts ?? null}
      />

      {loading && !data ? (
        <div className="text-center text-text-muted py-20">Loading...</div>
      ) : !s || s.total_hands === 0 ? (
        <EmptyState
          variant={hasFilters ? 'no-match' : 'no-data'}
          onClearFilters={hasFilters ? () => { setStakes(''); setDateFrom(''); setDateTo(''); } : undefined}
        />
      ) : (
        <>
          {/* ── Financial Summary ── */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3">
            <SummaryCard label="Paid to Fund" value={`${s.total_paid_bb.toFixed(0)} BB`} sub={`$${s.total_paid_usd.toFixed(2)} (${s.pots_won} pots won)`} color="text-red" />
            <SummaryCard label="Received (EV)" value={`${s.total_received_bb.toFixed(0)} BB`} sub={`$${s.total_received_usd.toFixed(2)} (${s.cash_drop_hands} drops)`} color="text-green" />
            <SummaryCard label="Net" value={`${s.net_bb >= 0 ? '+' : ''}${s.net_bb.toFixed(0)} BB`} sub={`$${s.net_usd >= 0 ? '+' : ''}${s.net_usd.toFixed(2)}`} color={s.net_bb >= 0 ? 'text-green' : 'text-red'} />
            <SummaryCard label="Frequency" value={s.cash_drop_hands > 0 ? `1 in ${s.frequency.toFixed(0)}` : '--'} sub={`${s.cash_drop_hands} drops in ${s.total_hands.toLocaleString()} hands`} />
          </div>

          {/* ── Cash Drop Pots: Hero + Field ── */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mb-3">
            <Card className="gap-0 py-0 p-3">
              <div className="flex items-center justify-between mb-2">
                <h2 className="text-sm font-medium text-text-muted uppercase tracking-wide">Hero in Cash Drop Pots</h2>
                <span className="text-xs text-text-muted">{s.cash_drop_hands} hands</span>
              </div>
              <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-[15px]">
                <StatRow label="Won" value={s.hero_won_bb} suffix=" BB" color />
                <StatRow label="bb/100" value={s.hero_bb100} color />
                <StatRow label="VPIP" value={s.hero_vpip_pct} suffix="%" />
                <StatRow label="PFR" value={s.hero_pfr_pct} suffix="%" />
                <StatRow label="3-Bet" value={s.hero_three_bet_pct} suffix="%" />
                <StatRow label="Limp" value={s.hero_limp_pct} suffix="%" />
                <StatRow label="All-in" value={s.hero_allin_raise_pct} suffix="%" />
                <StatRow label="AI Call" value={s.hero_allin_call_pct} suffix="%" />
                <StatRow label="WTSD" value={s.hero_wtsd_pct} suffix="%" />
                <StatRow label="W$SD" value={s.hero_wsd_pct} suffix="%" />
              </div>
            </Card>

            {data!.field ? (
              <Card className="gap-0 py-0 p-3">
                <div className="flex items-center justify-between mb-2">
                  <h2 className="text-sm font-medium text-text-muted uppercase tracking-wide">Field in Cash Drop Pots</h2>
                  <span className="text-xs text-text-muted">{data!.field.total_players} player-hands</span>
                </div>
                <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-[15px]">
                  <StatRow label="Avg Players" value={data!.field.avg_players_per_pot} />
                  <StatRow label="Avg bb Won" value={data!.field.avg_won_bb} color />
                  <StatRow label="VPIP" value={data!.field.vpip_pct} suffix="%" />
                  <StatRow label="PFR" value={data!.field.pfr_pct} suffix="%" />
                  <StatRow label="3-Bet" value={data!.field.three_bet_pct} suffix="%" />
                  <StatRow label="Limp" value={data!.field.limp_pct} suffix="%" />
                  <StatRow label="All-in" value={data!.field.allin_raise_pct} suffix="%" />
                  <StatRow label="AI Call" value={data!.field.allin_call_pct} suffix="%" />
                  <StatRow label="WTSD" value={data!.field.wtsd_pct} suffix="%" />
                  <StatRow label="W$SD" value={data!.field.wsd_pct} suffix="%" />
                </div>
              </Card>
            ) : (
              <Card className="p-5 text-text-muted text-sm flex items-center justify-center">
                No field data available
              </Card>
            )}
          </div>

          {/* ── Drop Size Breakdown ── */}
          {data!.by_type.length > 0 && (
            <Card className="gap-0 py-0 p-3 mb-2">
              <h2 className="text-sm font-medium text-text-muted uppercase tracking-wide mb-2">Drop Size Breakdown</h2>
              <div className="flex gap-4 flex-wrap">
                {data!.by_type.map(t => (
                  <div key={t.drop_bb} className="flex items-baseline gap-2">
                    <span className="font-mono font-medium">{t.drop_bb.toFixed(0)} BB</span>
                    <span className="text-text-muted text-sm">{t.count}x</span>
                    <span className="text-green font-mono text-sm">${t.total_usd.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* ── Field Ranges by Action Type ── */}
          {data!.ranges.length > 0 && (
            <div>
              <h2 className="text-sm font-medium text-text-muted uppercase tracking-wide mb-2">
                Field Ranges in Cash Drop Pots
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {data!.ranges.map(cat => (
                  <FieldHeatmap key={cat.label} category={cat} />
                ))}
              </div>
              <div className="flex items-center gap-4 mt-2 text-[10px] text-text-muted">
                <span><span className="text-primary font-mono">AKs</span> suited</span>
                <span><span className="text-yellow font-mono">AA</span> pair</span>
                <span>Brighter = more hands</span>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function StatRow({ label, value, suffix, color }: { label: string; value: number | null; suffix?: string; color?: boolean }) {
  const text = value !== null ? value.toFixed(1) + (suffix ?? '') : '--';
  const cls = color && value !== null
    ? value >= 0 ? 'text-green' : 'text-red'
    : 'text-text';
  return (
    <div className="flex justify-between items-baseline">
      <span className="text-text-muted">{label}</span>
      <span className={`font-mono font-medium ${cls}`}>{text}</span>
    </div>
  );
}

function SummaryCard({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <Card className="gap-0 py-0">
      <CardContent className="px-3 py-2">
        <div className="text-[10px] text-text-muted uppercase tracking-wide mb-0.5">{label}</div>
        <div className={`text-sm font-bold font-mono ${color ?? 'text-text'}`}>{value}</div>
        {sub && <div className="text-[11px] text-text-muted mt-0.5">{sub}</div>}
      </CardContent>
    </Card>
  );
}
