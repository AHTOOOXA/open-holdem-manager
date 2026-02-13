import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  getPopulationOverview,
  getPopulationPreflop,
  getPopulationSegments,
  getPopulationPostflop,
  getPopulationPotTypes,
  getPopulationShowdown,
  getPopulationHuVsMw,
  getPopulationComparison,
} from '@/lib/api';
import type { PopulationFilterParams, PositionStat } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import ConfidenceBadge from '@/components/population/ConfidenceBadge';
import SegmentComparison from '@/components/population/SegmentComparison';
import EmptyState from '@/components/EmptyState';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

const POSITIONS = ['EP', 'MP', 'CO', 'BTN', 'SB', 'BB'];

function fmt(v: number | null, decimals = 1): string {
  if (v === null || v === undefined) return '\u2014';
  return v.toFixed(decimals);
}

function PositionBar({ stats, label }: { stats: PositionStat[]; label: string }) {
  return (
    <div>
      <div className="text-[12px] uppercase tracking-wider text-text-muted mb-1.5">{label}</div>
      <div className="grid grid-cols-6 gap-1">
        {POSITIONS.map((pos) => {
          const s = stats.find((st) => st.position === pos);
          const val = s?.value;
          const sample = s?.sample ?? 0;
          // Color intensity based on value
          const intensity = val !== null && val !== undefined ? Math.min(val / 50, 1) : 0;
          const bg = val !== null && val !== undefined
            ? `rgba(99, 102, 241, ${0.1 + intensity * 0.4})`
            : 'transparent';

          return (
            <div key={pos} className="text-center rounded p-1.5 border border-border/50" style={{ backgroundColor: bg }}>
              <div className="text-[11px] text-text-muted mb-0.5">{pos}</div>
              <div className="text-[14px] font-mono font-semibold">{fmt(val)}</div>
              <ConfidenceBadge sample={sample} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Section({ title, defaultOpen = true, children }: { title: string; defaultOpen?: boolean; children: React.ReactNode }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="mb-4">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 text-[13px] font-semibold uppercase tracking-wider text-text-muted hover:text-text mb-2"
      >
        <span className="text-[10px]">{open ? '\u25BC' : '\u25B6'}</span>
        {title}
      </button>
      {open && children}
    </div>
  );
}

export default function PopulationPage() {
  const [minHands, setMinHands] = useState(20);
  const [excludeHero, setExcludeHero] = useState(true);
  const [showComparison, setShowComparison] = useState(false);

  const filterParams: PopulationFilterParams = {
    min_hands: minHands,
    exclude_hero: excludeHero,
  };

  const { data: overview, isPending: overviewLoading } = useQuery({
    queryKey: queryKeys.population.overview(filterParams),
    queryFn: () => getPopulationOverview(filterParams),
  });

  const { data: preflop } = useQuery({
    queryKey: queryKeys.population.preflop(filterParams),
    queryFn: () => getPopulationPreflop(filterParams),
  });

  const { data: segments } = useQuery({
    queryKey: queryKeys.population.segments(filterParams),
    queryFn: () => getPopulationSegments(filterParams),
  });

  const { data: postflop } = useQuery({
    queryKey: queryKeys.population.postflop(filterParams),
    queryFn: () => getPopulationPostflop(filterParams),
  });

  const { data: potTypes } = useQuery({
    queryKey: queryKeys.population.potTypes(filterParams),
    queryFn: () => getPopulationPotTypes(filterParams),
  });

  const { data: showdown } = useQuery({
    queryKey: queryKeys.population.showdown(filterParams),
    queryFn: () => getPopulationShowdown(filterParams),
  });

  const { data: huVsMw } = useQuery({
    queryKey: queryKeys.population.huVsMw(filterParams),
    queryFn: () => getPopulationHuVsMw(filterParams),
  });

  const { data: comparison } = useQuery({
    queryKey: queryKeys.population.comparison(filterParams),
    queryFn: () => getPopulationComparison(filterParams),
    enabled: showComparison,
  });

  if (overviewLoading) {
    return <p className="text-text-muted text-sm py-8 text-center">Loading population data...</p>;
  }

  if (!overview || overview.player_count === 0) {
    return <EmptyState variant="no-data" />;
  }

  return (
    <div>
      {/* Filters */}
      <div className="flex items-center gap-4 mb-4 flex-wrap">
        <div className="flex items-center gap-1.5">
          <span className="text-[12px] text-text-muted">Min hands:</span>
          <Input
            type="number"
            min={0}
            value={minHands}
            onChange={(e) => setMinHands(Number(e.target.value) || 0)}
            className="w-20 h-8 text-[13px]"
          />
        </div>
        <label className="flex items-center gap-1.5 cursor-pointer">
          <Checkbox
            checked={excludeHero}
            onCheckedChange={(checked) => setExcludeHero(checked === true)}
          />
          <span className="text-[12px] text-text-muted">Exclude Hero</span>
        </label>
        <label className="flex items-center gap-1.5 cursor-pointer">
          <Checkbox
            checked={showComparison}
            onCheckedChange={(checked) => setShowComparison(checked === true)}
          />
          <span className="text-[12px] text-text-muted">Show Hero Comparison</span>
        </label>
      </div>

      {/* Overview */}
      <div className="flex items-center gap-6 mb-4 text-[14px]">
        <span className="text-text-muted">
          Pool: <span className="font-mono text-text">{overview.player_count.toLocaleString()}</span> players
        </span>
        <span className="text-text-muted">
          Observations: <span className="font-mono text-text">{overview.observation_count.toLocaleString()}</span>
        </span>
      </div>

      {/* Hero Comparison */}
      {showComparison && comparison && comparison.stats.length > 0 && (
        <Section title="Hero vs Population">
          <Table>
            <TableHeader>
              <TableRow className="text-[12px] uppercase tracking-wide">
                <TableHead className="py-1 px-2 h-auto">Stat</TableHead>
                <TableHead className="py-1 px-2 h-auto text-right">Hero</TableHead>
                <TableHead className="py-1 px-2 h-auto text-right">Population</TableHead>
                <TableHead className="py-1 px-2 h-auto text-right">Diff</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {comparison.stats.map((s) => (
                <TableRow key={s.stat} className="text-[13px]">
                  <TableCell className="py-1 px-2 text-text-muted">{s.stat}</TableCell>
                  <TableCell className="py-1 px-2 text-right font-mono">{fmt(s.hero_value)}</TableCell>
                  <TableCell className="py-1 px-2 text-right font-mono">{fmt(s.pop_value)}</TableCell>
                  <TableCell className={`py-1 px-2 text-right font-mono font-semibold ${
                    s.diff !== null ? (s.diff > 0 ? 'text-green' : s.diff < 0 ? 'text-red' : 'text-text') : 'text-text-muted'
                  }`}>
                    {s.diff !== null ? `${s.diff > 0 ? '+' : ''}${s.diff.toFixed(1)}` : '\u2014'}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Section>
      )}

      {/* Preflop */}
      {preflop && (
        <Section title="Preflop">
          <div className="space-y-4">
            <PositionBar stats={preflop.vpip_by_position} label="VPIP by Position" />
            <PositionBar stats={preflop.pfr_by_position} label="PFR by Position" />
            <PositionBar stats={preflop.open_raise} label="Open Raise by Position" />
            <PositionBar stats={preflop.limp_by_position} label="Limp by Position" />
            <PositionBar stats={preflop.four_bet} label="4-Bet by Position" />
          </div>
        </Section>
      )}

      {/* Postflop */}
      {postflop && postflop.lines.length > 0 && (
        <Section title="Postflop" defaultOpen={false}>
          <Table>
            <TableHeader>
              <TableRow className="text-[12px] uppercase tracking-wide">
                <TableHead className="py-1 px-2 h-auto">Stat</TableHead>
                <TableHead className="py-1 px-2 h-auto text-right">Value</TableHead>
                <TableHead className="py-1 px-2 h-auto text-right">Sample</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {postflop.lines.map((l, i) => (
                <TableRow key={i} className="text-[13px]">
                  <TableCell className="py-1 px-2 text-text-muted">
                    {l.street !== 'all' ? `${l.street} ` : ''}{l.stat.replace(/_/g, ' ')}
                  </TableCell>
                  <TableCell className="py-1 px-2 text-right font-mono">
                    {fmt(l.value)}
                  </TableCell>
                  <TableCell className="py-1 px-2 text-right">
                    <ConfidenceBadge sample={l.sample} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Section>
      )}

      {/* Pot Types */}
      {potTypes && potTypes.pot_types.length > 0 && (
        <Section title="By Pot Type" defaultOpen={false}>
          <Table>
            <TableHeader>
              <TableRow className="text-[12px] uppercase tracking-wide">
                <TableHead className="py-1 px-2 h-auto">Pot Type</TableHead>
                <TableHead className="py-1 px-2 h-auto text-right">Hands</TableHead>
                <TableHead className="py-1 px-2 h-auto text-right">C-Bet Flop</TableHead>
                <TableHead className="py-1 px-2 h-auto text-right">Fold to CB</TableHead>
                <TableHead className="py-1 px-2 h-auto text-right">WTSD</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {potTypes.pot_types.map((pt) => (
                <TableRow key={pt.pot_type} className="text-[13px]">
                  <TableCell className="py-1 px-2 font-mono">{pt.pot_type}</TableCell>
                  <TableCell className="py-1 px-2 text-right font-mono text-text-muted">{pt.hands.toLocaleString()}</TableCell>
                  <TableCell className="py-1 px-2 text-right font-mono">{fmt(pt.cbet_flop)}</TableCell>
                  <TableCell className="py-1 px-2 text-right font-mono">{fmt(pt.fold_to_cbet_flop)}</TableCell>
                  <TableCell className="py-1 px-2 text-right font-mono">{fmt(pt.wtsd)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Section>
      )}

      {/* Showdown */}
      {showdown && showdown.by_position.length > 0 && (
        <Section title="Showdown & Aggression" defaultOpen={false}>
          <div className="space-y-3">
            <Table>
              <TableHeader>
                <TableRow className="text-[12px] uppercase tracking-wide">
                  <TableHead className="py-1 px-2 h-auto">Position</TableHead>
                  <TableHead className="py-1 px-2 h-auto text-right">WTSD</TableHead>
                  <TableHead className="py-1 px-2 h-auto text-right">WSD</TableHead>
                  <TableHead className="py-1 px-2 h-auto text-right">WWSF</TableHead>
                  <TableHead className="py-1 px-2 h-auto text-right">Sample</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {showdown.by_position.map((p) => (
                  <TableRow key={p.position} className="text-[13px]">
                    <TableCell className="py-1 px-2 font-mono">{p.position}</TableCell>
                    <TableCell className="py-1 px-2 text-right font-mono">{fmt(p.wtsd)}</TableCell>
                    <TableCell className="py-1 px-2 text-right font-mono">{fmt(p.wsd)}</TableCell>
                    <TableCell className="py-1 px-2 text-right font-mono">{fmt(p.wwsf)}</TableCell>
                    <TableCell className="py-1 px-2 text-right">
                      <ConfidenceBadge sample={p.sample} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <div className="grid grid-cols-3 gap-4 text-[13px]">
              {[
                { label: 'AF Flop', value: showdown.af_flop },
                { label: 'AF Turn', value: showdown.af_turn },
                { label: 'AF River', value: showdown.af_river },
                { label: 'AFq Flop', value: showdown.afq_flop },
                { label: 'AFq Turn', value: showdown.afq_turn },
                { label: 'AFq River', value: showdown.afq_river },
              ].map((s) => (
                <div key={s.label} className="bg-surface/50 rounded border border-border/50 p-2">
                  <div className="text-[11px] text-text-muted uppercase mb-0.5">{s.label}</div>
                  <div className="font-mono font-semibold">{s.value !== null ? s.value.toFixed(s.label.startsWith('AF ') ? 2 : 1) : '\u2014'}</div>
                </div>
              ))}
            </div>
          </div>
        </Section>
      )}

      {/* HU vs MW */}
      {huVsMw && huVsMw.stats.length > 0 && (
        <Section title="Heads-Up vs Multiway" defaultOpen={false}>
          <Table>
            <TableHeader>
              <TableRow className="text-[12px] uppercase tracking-wide">
                <TableHead className="py-1 px-2 h-auto">Type</TableHead>
                <TableHead className="py-1 px-2 h-auto text-right">Hands</TableHead>
                <TableHead className="py-1 px-2 h-auto text-right">C-Bet Flop</TableHead>
                <TableHead className="py-1 px-2 h-auto text-right">Fold to CB</TableHead>
                <TableHead className="py-1 px-2 h-auto text-right">WTSD</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {huVsMw.stats.map((s) => (
                <TableRow key={s.category} className="text-[13px]">
                  <TableCell className="py-1 px-2 font-mono">{s.category}</TableCell>
                  <TableCell className="py-1 px-2 text-right font-mono text-text-muted">{s.hands.toLocaleString()}</TableCell>
                  <TableCell className="py-1 px-2 text-right font-mono">{fmt(s.cbet_flop)}</TableCell>
                  <TableCell className="py-1 px-2 text-right font-mono">{fmt(s.fold_to_cbet_flop)}</TableCell>
                  <TableCell className="py-1 px-2 text-right font-mono">{fmt(s.wtsd)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Section>
      )}

      {/* Segmentation */}
      {segments && segments.segments.length > 0 && (
        <Section title="Player Segmentation">
          <SegmentComparison segments={segments.segments} />
        </Section>
      )}
    </div>
  );
}
