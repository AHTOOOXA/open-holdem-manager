import type { HeroStats, DriftStat, StatValue } from '@/lib/api';
import { Card } from '@/components/ui/card';
import { PosTable, InlineStat, posRow, svDelta } from '@/components/stats/StatDisplay';

interface StatsCardProps {
  stats: HeroStats;
  decimals: 0 | 1;
  driftMap?: Map<string, DriftStat>;
  onStatClick?: (key: string, pos?: string) => void;
  /** When provided, each stat shows a (+-X) delta = stats - compareStats */
  compareStats?: HeroStats;
}

const fullPosHeaders = ['Tot', 'EP', 'MP', 'CO', 'BTN', 'SB', 'BB'];
const fullPosKeys: ('total' | 'ep' | 'mp' | 'co' | 'btn' | 'sb' | 'bb')[] = ['total', 'ep', 'mp', 'co', 'btn', 'sb', 'bb'];

export default function StatsCard({ stats, decimals, driftMap, onStatClick, compareStats: cs }: StatsCardProps) {
  /** Shorthand: compute delta for two StatValues */
  function d(a: StatValue | undefined, b: StatValue | undefined): number | null | undefined {
    return cs ? svDelta(a, b) : undefined;
  }

  /** Build a steal/vs-steal cell with optional delta */
  function sc(sv: StatValue, pos: string, cSv: StatValue | undefined, opts: { statKey?: string; drillKey?: string }) {
    return { sv, position: pos, ...opts, delta: d(sv, cSv) };
  }

  return (
    <Card className="gap-0 py-0 overflow-hidden">

      {/* ── PRE-FLOP ── */}
      <div className="px-3 py-1.5 border-b border-border">
        <div className="text-[11px] font-bold uppercase tracking-wider text-primary">Pre-Flop</div>
      </div>
      <div className="flex flex-col lg:flex-row">
        {/* Left: Positional table */}
        <div className="flex-1 min-w-0 overflow-x-auto lg:border-r border-border">
          <PosTable
            headers={fullPosHeaders}
            defaultDecimals={decimals}
            driftMap={driftMap}
            onStatClick={onStatClick}
            rows={[
              posRow('VPIP',          stats.vpip,            'vpip',         fullPosKeys, undefined, undefined, cs?.vpip),
              posRow('PFR',           stats.pfr,             'pfr',          fullPosKeys, undefined, undefined, cs?.pfr),
              posRow('Open Raise',    stats.open_raise,      'open_raise',   fullPosKeys, undefined, undefined, cs?.open_raise),
              posRow('Limp',          stats.limp,            'limp',         fullPosKeys, undefined, true,      cs?.limp),
              posRow('Call Open',     stats.call_open_raise, undefined,      fullPosKeys, 'call_open_raise', undefined, cs?.call_open_raise),
              posRow('3-Bet',         stats.three_bet,       'three_bet',    fullPosKeys, undefined, true,      cs?.three_bet),
              posRow('Fold to 3-Bet', stats.fold_to_3bet,    'fold_to_3bet', fullPosKeys, undefined, undefined, cs?.fold_to_3bet),
              posRow('4-Bet',         stats.four_bet,        'four_bet',     fullPosKeys, undefined, true,      cs?.four_bet),
              posRow('Fold to 4-Bet', stats.fold_to_4bet,    'fold_to_4bet', fullPosKeys, undefined, undefined, cs?.fold_to_4bet),
            ]}
          />
        </div>

        {/* Right: Preflop extras */}
        <div className="w-full lg:w-40 lg:shrink-0">
          <PosTable
            headers={[]}
            defaultDecimals={decimals}
            driftMap={driftMap}
            onStatClick={onStatClick}
            rows={[
              { label: 'Squeeze', cells: [{ sv: stats.squeeze, drillKey: 'squeeze', delta: d(stats.squeeze, cs?.squeeze) }] },
              { label: '5-Bet', cells: [{ sv: stats.five_bet, drillKey: 'five_bet', delta: d(stats.five_bet, cs?.five_bet) }] },
              { label: 'Call 4-Bet', cells: [{ sv: stats.call_4bet, drillKey: 'call_4bet', delta: d(stats.call_4bet, cs?.call_4bet) }] },
              { label: 'Limp-Fold', cells: [{ sv: stats.limp_fold, drillKey: 'limp_fold', delta: d(stats.limp_fold, cs?.limp_fold) }] },
              { label: '4-Bet-Fold', cells: [{ sv: stats.four_bet_fold, drillKey: 'four_bet_fold', delta: d(stats.four_bet_fold, cs?.four_bet_fold) }] },
            ]}
          />
        </div>
      </div>

      {/* ── STEAL ── */}
      <div className="px-3 py-1.5 border-y border-border">
        <div className="text-[11px] font-bold uppercase tracking-wider text-primary">Steal</div>
      </div>
      <div className="flex flex-col lg:flex-row">
        {/* Left: Steal table (Total, BTN, SB) */}
        <div className="flex-1 min-w-0 overflow-x-auto lg:border-r border-border">
          <PosTable
            headers={['Tot', 'BTN', 'SB']}
            defaultDecimals={decimals}
            driftMap={driftMap}
            onStatClick={onStatClick}
            rows={[
              {
                label: 'Steal',
                cells: [
                  sc(stats.steal.total, 'total', cs?.steal.total, { statKey: 'steal', drillKey: 'steal' }),
                  sc(stats.steal.btn, 'btn', cs?.steal.btn, { statKey: 'steal', drillKey: 'steal' }),
                  sc(stats.steal.sb, 'sb', cs?.steal.sb, { statKey: 'steal', drillKey: 'steal' }),
                ],
              },
              {
                label: 'Fold to 3Bet',
                cells: [
                  sc(stats.fold_to_3bet_steal.total, 'total', cs?.fold_to_3bet_steal.total, { statKey: 'fold_to_3bet', drillKey: 'fold_to_3bet' }),
                  sc(stats.fold_to_3bet_steal.btn, 'btn', cs?.fold_to_3bet_steal.btn, { statKey: 'fold_to_3bet', drillKey: 'fold_to_3bet' }),
                  sc(stats.fold_to_3bet_steal.sb, 'sb', cs?.fold_to_3bet_steal.sb, { statKey: 'fold_to_3bet', drillKey: 'fold_to_3bet' }),
                ],
              },
              {
                label: '4-Bet',
                cells: [
                  sc(stats.four_bet_steal.total, 'total', cs?.four_bet_steal.total, { statKey: 'four_bet', drillKey: 'four_bet' }),
                  sc(stats.four_bet_steal.btn, 'btn', cs?.four_bet_steal.btn, { statKey: 'four_bet', drillKey: 'four_bet' }),
                  sc(stats.four_bet_steal.sb, 'sb', cs?.four_bet_steal.sb, { statKey: 'four_bet', drillKey: 'four_bet' }),
                ],
              },
              {
                label: '4-Bet-Fold',
                cells: [
                  sc(stats.four_bet_fold_steal.total, 'total', cs?.four_bet_fold_steal.total, { drillKey: 'four_bet_fold_steal' }),
                  sc(stats.four_bet_fold_steal.btn, 'btn', cs?.four_bet_fold_steal.btn, { drillKey: 'four_bet_fold_steal' }),
                  sc(stats.four_bet_fold_steal.sb, 'sb', cs?.four_bet_fold_steal.sb, { drillKey: 'four_bet_fold_steal' }),
                ],
              },
            ]}
          />
        </div>

        {/* Right: vs Steal (SB, BB) */}
        <div className="flex-1 min-w-0 overflow-x-auto">
          <div className="px-3 py-1 text-[10px] text-text-muted uppercase tracking-widest font-semibold border-b border-border/30">
            vs. Steal
          </div>
          <PosTable
            headers={['SB', 'BB']}
            defaultDecimals={decimals}
            driftMap={driftMap}
            onStatClick={onStatClick}
            rows={[
              {
                label: 'Fold',
                cells: [
                  sc(stats.vs_steal_fold.sb, 'sb', cs?.vs_steal_fold.sb, { statKey: 'vs_steal_fold', drillKey: 'fold_to_steal' }),
                  sc(stats.vs_steal_fold.bb, 'bb', cs?.vs_steal_fold.bb, { statKey: 'vs_steal_fold', drillKey: 'fold_to_steal' }),
                ],
              },
              {
                label: 'Call',
                cells: [
                  sc(stats.vs_steal_call.sb, 'sb', cs?.vs_steal_call.sb, { drillKey: 'call_steal' }),
                  sc(stats.vs_steal_call.bb, 'bb', cs?.vs_steal_call.bb, { drillKey: 'call_steal' }),
                ],
              },
              {
                label: '3-Bet',
                cells: [
                  sc(stats.vs_steal_3bet.sb, 'sb', cs?.vs_steal_3bet.sb, { drillKey: 'three_bet_vs_steal' }),
                  sc(stats.vs_steal_3bet.bb, 'bb', cs?.vs_steal_3bet.bb, { drillKey: 'three_bet_vs_steal' }),
                ],
              },
            ]}
          />
        </div>
      </div>

      {/* ── POSTFLOP ── */}
      <div className="px-3 py-1.5 border-y border-border">
        <div className="text-[11px] font-bold uppercase tracking-wider text-primary">Postflop</div>
      </div>
      <div className="flex flex-col lg:flex-row">
        {/* Left: Postflop stats by street */}
        <div className="flex-1 min-w-0 overflow-x-auto lg:border-r border-border">
          <PosTable
            headers={['Flop', 'Turn', 'River']}
            defaultDecimals={decimals}
            driftMap={driftMap}
            onStatClick={onStatClick}
            rows={[
              {
                label: 'C-Bet',
                cells: [
                  sc(stats.cbet_flop.total, 'total', cs?.cbet_flop.total, { statKey: 'cbet_flop', drillKey: 'cbet_flop' }),
                  sc(stats.cbet_turn.total, 'total', cs?.cbet_turn.total, { statKey: 'cbet_turn', drillKey: 'cbet_turn' }),
                  sc(stats.cbet_river.total, 'total', cs?.cbet_river.total, { statKey: 'cbet_river', drillKey: 'cbet_river' }),
                ],
              },
              {
                label: 'Fold to CBet',
                cells: [
                  sc(stats.fold_to_cbet_flop.total, 'total', cs?.fold_to_cbet_flop.total, { statKey: 'fold_to_cbet_flop', drillKey: 'fold_to_cbet_flop' }),
                  sc(stats.fold_to_cbet_turn.total, 'total', cs?.fold_to_cbet_turn.total, { statKey: 'fold_to_cbet_turn', drillKey: 'fold_to_cbet_turn' }),
                  sc(stats.fold_to_cbet_river.total, 'total', cs?.fold_to_cbet_river.total, { drillKey: 'fold_to_cbet_river' }),
                ],
              },
              {
                label: 'Aggression',
                cells: [
                  { sv: stats.af_flop, statKey: 'af_flop', drillKey: 'af_flop', decimals: 1 as const, delta: d(stats.af_flop, cs?.af_flop) },
                  { sv: stats.af_turn, statKey: 'af_turn', drillKey: 'af_turn', decimals: 1 as const, delta: d(stats.af_turn, cs?.af_turn) },
                  { sv: stats.af_river, statKey: 'af_river', drillKey: 'af_river', decimals: 1 as const, delta: d(stats.af_river, cs?.af_river) },
                ],
              },
              {
                label: 'Agg Freq',
                cells: [
                  { sv: stats.afq_flop, drillKey: 'afq_flop', delta: d(stats.afq_flop, cs?.afq_flop) },
                  { sv: stats.afq_turn, drillKey: 'afq_turn', delta: d(stats.afq_turn, cs?.afq_turn) },
                  { sv: stats.afq_river, drillKey: 'afq_river', delta: d(stats.afq_river, cs?.afq_river) },
                ],
              },
              {
                label: 'Donk Bet',
                cells: [
                  { sv: stats.donk_bet_flop, drillKey: 'donk_bet_flop', delta: d(stats.donk_bet_flop, cs?.donk_bet_flop) },
                  { sv: stats.donk_bet_turn, drillKey: 'donk_bet_turn', delta: d(stats.donk_bet_turn, cs?.donk_bet_turn) },
                  { sv: stats.donk_bet_river, drillKey: 'donk_bet_river', delta: d(stats.donk_bet_river, cs?.donk_bet_river) },
                ],
              },
            ]}
          />
        </div>

        {/* Right: vs CBet Flop (Fold/Call/Raise) */}
        <div className="flex-1 min-w-0 overflow-x-auto">
          <div className="px-3 py-1 text-[10px] text-text-muted uppercase tracking-widest font-semibold border-b border-border/30">
            vs. C-Bet Flop
          </div>
          <PosTable
            headers={['Fold', 'Call', 'Raise']}
            defaultDecimals={decimals}
            driftMap={driftMap}
            onStatClick={onStatClick}
            rows={[
              {
                label: 'Raised Pot',
                cells: [
                  { sv: stats.fold_cbet_flop_raised, drillKey: 'fold_cbet_flop_raised', delta: d(stats.fold_cbet_flop_raised, cs?.fold_cbet_flop_raised) },
                  { sv: stats.call_cbet_flop_raised, drillKey: 'call_cbet_flop_raised', delta: d(stats.call_cbet_flop_raised, cs?.call_cbet_flop_raised) },
                  { sv: stats.raise_cbet_flop_raised, drillKey: 'raise_cbet_flop_raised', delta: d(stats.raise_cbet_flop_raised, cs?.raise_cbet_flop_raised) },
                ],
              },
              {
                label: '3-Bet Pot',
                cells: [
                  { sv: stats.fold_cbet_flop_3bet, drillKey: 'fold_cbet_flop_3bet', delta: d(stats.fold_cbet_flop_3bet, cs?.fold_cbet_flop_3bet) },
                  { sv: stats.call_cbet_flop_3bet, drillKey: 'call_cbet_flop_3bet', delta: d(stats.call_cbet_flop_3bet, cs?.call_cbet_flop_3bet) },
                  { sv: stats.raise_cbet_flop_3bet, drillKey: 'raise_cbet_flop_3bet', delta: d(stats.raise_cbet_flop_3bet, cs?.raise_cbet_flop_3bet) },
                ],
              },
            ]}
          />
        </div>
      </div>

      {/* ── MISSED C-BET ── */}
      <div className="px-3 py-1.5 border-y border-border">
        <div className="text-[11px] font-bold uppercase tracking-wider text-primary">Missed C-Bet</div>
      </div>
      <div className="flex gap-0">
        {/* Left: Missed CBet breakdown */}
        <div className="flex-1 min-w-0 p-2 border-r border-border">
          <div className="space-y-1">
            <div className="flex items-baseline justify-between">
              <span className="text-[13px] text-text font-medium">Missed C-Bet</span>
              <InlineStat sv={stats.missed_cbet_flop} drillKey="missed_cbet_flop" delta={d(stats.missed_cbet_flop, cs?.missed_cbet_flop)} defaultDecimals={decimals} driftMap={driftMap} onStatClick={onStatClick} />
            </div>
            <div className="pl-4 border-l-2 border-border/30 ml-1 space-y-0.5">
              <div className="flex items-baseline justify-between">
                <span className="text-[12px] text-text-muted">In Position</span>
                <InlineStat sv={stats.missed_cbet_flop_ip} drillKey="missed_cbet_flop_ip" delta={d(stats.missed_cbet_flop_ip, cs?.missed_cbet_flop_ip)} defaultDecimals={decimals} driftMap={driftMap} onStatClick={onStatClick} />
              </div>
              <div className="flex items-baseline justify-between">
                <span className="text-[12px] text-text-muted">&rarr; Fold</span>
                <InlineStat sv={stats.missed_cbet_fold_ip} drillKey="missed_cbet_fold_ip" delta={d(stats.missed_cbet_fold_ip, cs?.missed_cbet_fold_ip)} defaultDecimals={decimals} driftMap={driftMap} onStatClick={onStatClick} />
              </div>
              <div className="flex items-baseline justify-between">
                <span className="text-[12px] text-text-muted">Out of Position</span>
                <InlineStat sv={stats.missed_cbet_flop_oop} drillKey="missed_cbet_flop_oop" delta={d(stats.missed_cbet_flop_oop, cs?.missed_cbet_flop_oop)} defaultDecimals={decimals} driftMap={driftMap} onStatClick={onStatClick} />
              </div>
              <div className="flex items-baseline justify-between">
                <span className="text-[12px] text-text-muted">&rarr; Fold</span>
                <InlineStat sv={stats.missed_cbet_fold_oop} drillKey="missed_cbet_fold_oop" delta={d(stats.missed_cbet_fold_oop, cs?.missed_cbet_fold_oop)} defaultDecimals={decimals} driftMap={driftMap} onStatClick={onStatClick} />
              </div>
            </div>
          </div>
        </div>

        {/* Right: vs Missed CBet */}
        <div className="flex-1 min-w-0 p-2">
          <div className="space-y-1">
            <div className="flex items-baseline justify-between">
              <span className="text-[13px] text-text font-medium">vs. Missed C-Bet</span>
              <InlineStat sv={stats.vs_missed_cbet} drillKey="vs_missed_cbet" delta={d(stats.vs_missed_cbet, cs?.vs_missed_cbet)} defaultDecimals={decimals} driftMap={driftMap} onStatClick={onStatClick} />
            </div>
            <div className="pl-4 border-l-2 border-border/30 ml-1 space-y-0.5">
              <div className="flex items-baseline justify-between">
                <span className="text-[12px] text-text-muted">Bet In Position</span>
                <InlineStat sv={stats.vs_missed_cbet_bet_ip} drillKey="vs_missed_cbet_bet_ip" delta={d(stats.vs_missed_cbet_bet_ip, cs?.vs_missed_cbet_bet_ip)} defaultDecimals={decimals} driftMap={driftMap} onStatClick={onStatClick} />
              </div>
              <div className="flex items-baseline justify-between">
                <span className="text-[12px] text-text-muted">Check | Fold</span>
                <InlineStat sv={stats.vs_missed_cbet_check_fold_ip} drillKey="vs_missed_cbet_check_fold_ip" delta={d(stats.vs_missed_cbet_check_fold_ip, cs?.vs_missed_cbet_check_fold_ip)} defaultDecimals={decimals} driftMap={driftMap} onStatClick={onStatClick} />
              </div>
              <div className="flex items-baseline justify-between">
                <span className="text-[12px] text-text-muted">Bet OOP Turn</span>
                <InlineStat sv={stats.vs_missed_cbet_bet_oop_turn} drillKey="vs_missed_cbet_bet_oop_turn" delta={d(stats.vs_missed_cbet_bet_oop_turn, cs?.vs_missed_cbet_bet_oop_turn)} defaultDecimals={decimals} driftMap={driftMap} onStatClick={onStatClick} />
              </div>
              <div className="flex items-baseline justify-between">
                <span className="text-[12px] text-text-muted">Check-Fold</span>
                <InlineStat sv={stats.vs_missed_cbet_check_fold_oop} drillKey="vs_missed_cbet_check_fold_oop" delta={d(stats.vs_missed_cbet_check_fold_oop, cs?.vs_missed_cbet_check_fold_oop)} defaultDecimals={decimals} driftMap={driftMap} onStatClick={onStatClick} />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── SHOWDOWN ── */}
      <div className="px-3 py-1.5 border-y border-border">
        <div className="text-[11px] font-bold uppercase tracking-wider text-primary">Showdown</div>
      </div>
      <div className="grid grid-cols-3 divide-x divide-border">
        <div className="px-4 py-2 text-center">
          <div className="text-[12px] text-text-muted mb-1">WTSD</div>
          <InlineStat sv={stats.wtsd} statKey="wtsd" drillKey="went_to_showdown" delta={d(stats.wtsd, cs?.wtsd)} defaultDecimals={decimals} driftMap={driftMap} onStatClick={onStatClick} />
        </div>
        <div className="px-4 py-2 text-center">
          <div className="text-[12px] text-text-muted mb-1">W$SD</div>
          <InlineStat sv={stats.wsd} statKey="wsd" drillKey="won_at_showdown" delta={d(stats.wsd, cs?.wsd)} defaultDecimals={decimals} driftMap={driftMap} onStatClick={onStatClick} />
        </div>
        <div className="px-4 py-2 text-center">
          <div className="text-[12px] text-text-muted mb-1">WWSF</div>
          <InlineStat sv={stats.wwsf} statKey="wwsf" drillKey="wwsf" delta={d(stats.wwsf, cs?.wwsf)} defaultDecimals={decimals} driftMap={driftMap} onStatClick={onStatClick} />
        </div>
      </div>
    </Card>
  );
}
