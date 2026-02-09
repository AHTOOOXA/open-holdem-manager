import { useState, useEffect, useMemo, useCallback } from 'react';
import { getCashDropStats, getFilterOptions } from '@/lib/api';
import type { CashDropResponse, CashDropRangeCategory, ComboStats, FilterOptions } from '@/lib/api';

// ── Heatmap helpers ──────────────────────────────────────────────────

const RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'];

function comboKey(row: number, col: number): string {
  const r1 = RANKS[row];
  const r2 = RANKS[col];
  if (row === col) return r1 + r2;
  if (col > row) return r1 + r2 + 's';
  return r2 + r1 + 'o';
}

function comboLabel(row: number, col: number): string {
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

// ── Mini Heatmap Component ───────────────────────────────────────────

function MiniHeatmap({ category }: { category: CashDropRangeCategory }) {
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

  return (
    <div className="bg-surface rounded-lg border border-border p-4">
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

            return (
              <div
                key={`${row}-${col}`}
                className="flex items-center justify-center"
                style={{
                  backgroundColor: bg,
                  aspectRatio: '1',
                  border: '1px solid rgba(54,54,72,0.3)',
                }}
                title={`${key}: ${hands}`}
              >
                <span className={`text-[8px] font-mono leading-none ${
                  hands > 0
                    ? isSuited ? 'text-primary' : isPair ? 'text-yellow' : 'text-text'
                    : 'text-text-muted/40'
                }`}>
                  {comboLabel(row, col)}
                </span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

// ── Main Component ───────────────────────────────────────────────────

export default function CashDropPage() {
  const [data, setData] = useState<CashDropResponse | null>(null);
  const [filterOpts, setFilterOpts] = useState<FilterOptions | null>(null);
  const [loading, setLoading] = useState(true);
  const [stakes, setStakes] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  useEffect(() => {
    getFilterOptions().then(setFilterOpts).catch(() => {});
  }, []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (stakes) params.stakes = stakes;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      const result = await getCashDropStats(params);
      setData(result);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [stakes, dateFrom, dateTo]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const s = data?.summary;

  return (
    <div className="max-w-[1400px] mx-auto">
      {/* Header + Filters */}
      <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
        <h1 className="text-xl font-bold">Cash Drop Analysis</h1>
        <div className="flex items-center gap-3 flex-wrap">
          {filterOpts && filterOpts.stakes.length > 1 && (
            <select
              value={stakes}
              onChange={e => setStakes(e.target.value)}
              className="bg-surface border border-border rounded px-2.5 py-1 text-xs text-text"
            >
              <option value="">All Stakes</option>
              {filterOpts.stakes.map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          )}
          {filterOpts?.date_range?.min && (
            <>
              <input
                type="date"
                value={dateFrom}
                onChange={e => setDateFrom(e.target.value)}
                className="bg-surface border border-border rounded px-2 py-1 text-xs text-text"
              />
              <span className="text-text-muted text-xs">to</span>
              <input
                type="date"
                value={dateTo}
                onChange={e => setDateTo(e.target.value)}
                className="bg-surface border border-border rounded px-2 py-1 text-xs text-text"
              />
            </>
          )}
        </div>
      </div>

      {loading && !data ? (
        <div className="text-center text-text-muted py-20">Loading...</div>
      ) : !s || s.total_hands === 0 ? (
        <div className="text-center text-text-muted py-20">No data available</div>
      ) : (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
            <StatCard label="Paid to Fund" value={`${s.total_paid_bb.toFixed(0)} BB`} sub={`$${s.total_paid_usd.toFixed(2)} (${s.pots_won} pots won)`} color="text-red" />
            <StatCard label="Received (EV)" value={`${s.total_received_bb.toFixed(0)} BB`} sub={`$${s.total_received_usd.toFixed(2)} (${s.cash_drop_hands} drops / ${s.total_hands} hands)`} color="text-green" />
            <StatCard label="Net" value={`${s.net_bb >= 0 ? '+' : ''}${s.net_bb.toFixed(0)} BB`} sub={`$${s.net_usd >= 0 ? '+' : ''}${s.net_usd.toFixed(2)}`} color={s.net_bb >= 0 ? 'text-green' : 'text-red'} />
            <StatCard label="Frequency" value={s.frequency > 0 ? `1 in ${s.frequency.toFixed(0)}` : '--'} sub={`${s.cash_drop_hands} drops`} />
            <StatCard label="Avg Drop" value={s.avg_drop_bb > 0 ? `${s.avg_drop_bb.toFixed(0)} BB` : '--'} sub={`${s.eligible_hands} eligible pots`} />
          </div>

          {/* Hero Stats in Eligible Pots + Type Breakdown */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div className="bg-surface rounded-lg border border-border p-5">
              <h2 className="text-sm font-medium text-text-muted uppercase tracking-wide mb-3">Hero in Eligible Pots</h2>
              <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-[15px]">
                <StatRow label="Win %" value={s.win_pct} suffix="%" />
                <StatRow label="bb/100" value={s.win_rate_bb100} color />
                <StatRow label="VPIP" value={s.vpip_pct} suffix="%" />
                <StatRow label="PFR" value={s.pfr_pct} suffix="%" />
                <StatRow label="3-Bet" value={s.three_bet_pct} suffix="%" />
                <StatRow label="WTSD" value={s.wtsd_pct} suffix="%" />
                <StatRow label="W$SD" value={s.wsd_pct} suffix="%" />
              </div>
            </div>

          {data!.by_type.length > 0 && (
            <div className="bg-surface rounded-lg border border-border p-5">
              <h2 className="text-sm font-medium text-text-muted uppercase tracking-wide mb-3">Drop Types</h2>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-text-muted text-left border-b border-border">
                    <th className="py-2 pr-4">Size</th>
                    <th className="py-2 pr-4 text-right">Count</th>
                    <th className="py-2 text-right">Total USD</th>
                  </tr>
                </thead>
                <tbody>
                  {data!.by_type.map(t => (
                    <tr key={t.drop_bb} className="border-b border-border/50">
                      <td className="py-2 pr-4 font-mono font-medium">{t.drop_bb.toFixed(0)} BB</td>
                      <td className="py-2 pr-4 text-right">{t.count}</td>
                      <td className="py-2 text-right text-green font-mono">${t.total_usd.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          </div>

          {/* Range Heatmaps by Action Type */}
          {data!.ranges.length > 0 && (
            <div>
              <h2 className="text-sm font-medium text-text-muted uppercase tracking-wide mb-3">
                Field Ranges in Cash Drop Pots
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {data!.ranges.map(cat => (
                  <MiniHeatmap key={cat.label} category={cat} />
                ))}
              </div>
              <div className="flex items-center gap-5 mt-3 text-xs text-text-muted">
                <span><span className="text-primary font-mono">AKs</span> = suited</span>
                <span><span className="text-yellow font-mono">AA</span> = pair</span>
                <span><span className="text-text-muted font-mono">AKo</span> = offsuit</span>
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

function StatCard({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="bg-surface rounded-lg border border-border p-4">
      <div className="text-xs text-text-muted uppercase tracking-wide mb-1">{label}</div>
      <div className={`text-lg font-bold font-mono ${color ?? 'text-text'}`}>{value}</div>
      {sub && <div className="text-xs text-text-muted mt-0.5">{sub}</div>}
    </div>
  );
}
