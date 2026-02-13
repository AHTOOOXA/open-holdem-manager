import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getPlayer, getPlayerStats, getHeadToHead, updatePlayerNotes } from '@/lib/api';
import type { HeroStats, PositionalStats, StatValue } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import PlayerTypeBadge from '@/components/PlayerTypeBadge';
import HandExplorer from '@/components/hands/HandExplorer';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { formatRelativeDate } from '@/lib/utils';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

const POSITIONS = ['EP', 'MP', 'CO', 'BTN', 'SB', 'BB'] as const;

function fmt(sv: StatValue | undefined, decimals = 0): string {
  if (!sv || sv.sample === 0 || sv.value === null || sv.value === undefined) return '\u2014';
  return decimals > 0 ? sv.value.toFixed(decimals) : Math.round(sv.value).toString();
}

function fmtColor(sv: StatValue | undefined): string {
  if (!sv || sv.sample === 0 || sv.value === null) return 'text-text-muted';
  return 'text-text';
}

function PosRow({ label, stat, decimals = 0 }: { label: string; stat: PositionalStats; decimals?: number }) {
  return (
    <TableRow className="text-[13px]">
      <TableCell className="py-1 px-2 font-medium text-text-muted">{label}</TableCell>
      <TableCell className={`py-1 px-2 text-center font-mono font-semibold ${fmtColor(stat.total)}`}>
        {fmt(stat.total, decimals)}
      </TableCell>
      {POSITIONS.map((p) => {
        const sv = stat[p.toLowerCase() as keyof PositionalStats] as StatValue;
        return (
          <TableCell key={p} className={`py-1 px-2 text-center font-mono ${fmtColor(sv)}`}>
            {fmt(sv, decimals)}
          </TableCell>
        );
      })}
    </TableRow>
  );
}

function SVRow({ label, sv, decimals = 0 }: { label: string; sv: StatValue; decimals?: number }) {
  return (
    <TableRow className="text-[13px]">
      <TableCell className="py-1 px-2 font-medium text-text-muted">{label}</TableCell>
      <TableCell className={`py-1 px-2 text-center font-mono ${fmtColor(sv)}`} colSpan={7}>
        {fmt(sv, decimals)}{sv.sample > 0 ? ` (${sv.sample})` : ''}
      </TableCell>
    </TableRow>
  );
}

function StatsTab({ stats }: { stats: HeroStats }) {
  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="flex items-center gap-6 text-[14px]">
        <span className="text-text-muted">Hands: <span className="font-mono text-text">{stats.hands.toLocaleString()}</span></span>
        <span className="text-text-muted">
          Win rate:{' '}
          <span className={`font-mono font-semibold ${(stats.win_rate_bb100 ?? 0) >= 0 ? 'text-green' : 'text-red'}`}>
            {stats.win_rate_bb100 !== null ? `${stats.win_rate_bb100.toFixed(2)} bb/100` : '\u2014'}
          </span>
        </span>
        <span className="text-text-muted">
          EV:{' '}
          <span className={`font-mono ${(stats.win_rate_ev_bb100 ?? 0) >= 0 ? 'text-green' : 'text-red'}`}>
            {stats.win_rate_ev_bb100 !== null ? `${stats.win_rate_ev_bb100.toFixed(2)} bb/100` : '\u2014'}
          </span>
        </span>
      </div>

      {/* Positional stats table */}
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="text-[12px] uppercase tracking-wide">
              <TableHead className="py-1 px-2 h-auto w-32">Stat</TableHead>
              <TableHead className="py-1 px-2 h-auto text-center">Total</TableHead>
              {POSITIONS.map((p) => (
                <TableHead key={p} className="py-1 px-2 h-auto text-center">{p}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {/* Preflop */}
            <TableRow><TableCell colSpan={8} className="py-1 px-2 text-[11px] uppercase tracking-wider text-text-muted bg-surface/50 font-semibold">Preflop</TableCell></TableRow>
            <PosRow label="VPIP" stat={stats.vpip} />
            <PosRow label="PFR" stat={stats.pfr} />
            <PosRow label="Open Raise" stat={stats.open_raise} />
            <PosRow label="3-Bet" stat={stats.three_bet} />
            <PosRow label="4-Bet" stat={stats.four_bet} />
            <PosRow label="Fold to 3-Bet" stat={stats.fold_to_3bet} />
            <PosRow label="Fold to 4-Bet" stat={stats.fold_to_4bet} />
            <PosRow label="Call Open" stat={stats.call_open_raise} />
            <PosRow label="Limp" stat={stats.limp} />

            {/* Steal */}
            <TableRow><TableCell colSpan={8} className="py-1 px-2 text-[11px] uppercase tracking-wider text-text-muted bg-surface/50 font-semibold">Steal</TableCell></TableRow>
            <PosRow label="Steal" stat={stats.steal} />
            <PosRow label="vs Steal Fold" stat={stats.vs_steal_fold} />
            <PosRow label="vs Steal Call" stat={stats.vs_steal_call} />
            <PosRow label="vs Steal 3-Bet" stat={stats.vs_steal_3bet} />

            {/* Postflop */}
            <TableRow><TableCell colSpan={8} className="py-1 px-2 text-[11px] uppercase tracking-wider text-text-muted bg-surface/50 font-semibold">Postflop</TableCell></TableRow>
            <PosRow label="C-Bet Flop" stat={stats.cbet_flop} />
            <PosRow label="C-Bet Turn" stat={stats.cbet_turn} />
            <PosRow label="Fold to CB Flop" stat={stats.fold_to_cbet_flop} />
            <PosRow label="Fold to CB Turn" stat={stats.fold_to_cbet_turn} />

            {/* Aggression / Showdown */}
            <TableRow><TableCell colSpan={8} className="py-1 px-2 text-[11px] uppercase tracking-wider text-text-muted bg-surface/50 font-semibold">Aggression / Showdown</TableCell></TableRow>
            <SVRow label="AF Flop" sv={stats.af_flop} decimals={2} />
            <SVRow label="AF Turn" sv={stats.af_turn} decimals={2} />
            <SVRow label="AF River" sv={stats.af_river} decimals={2} />
            <SVRow label="AFq Flop" sv={stats.afq_flop} />
            <SVRow label="WTSD" sv={stats.wtsd} />
            <SVRow label="WSD" sv={stats.wsd} />
            <SVRow label="WWSF" sv={stats.wwsf} />
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

function H2HTab({ playerId }: { playerId: number }) {
  const { data, isPending } = useQuery({
    queryKey: queryKeys.players.h2h(playerId),
    queryFn: () => getHeadToHead(playerId),
  });

  if (isPending) return <p className="text-text-muted text-sm py-4">Loading...</p>;
  if (!data || data.total_hands === 0) return <p className="text-text-muted text-sm py-4">No hands played together.</p>;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-6 text-[14px]">
        <span className="text-text-muted">Hands together: <span className="font-mono text-text">{data.total_hands.toLocaleString()}</span></span>
        <span className="text-text-muted">
          Hero result:{' '}
          <span className={`font-mono font-semibold ${data.total_won_bb >= 0 ? 'text-green' : 'text-red'}`}>
            {data.total_won_bb >= 0 ? '+' : ''}{data.total_won_bb.toFixed(1)} BB ({data.overall_bb_per_100.toFixed(1)} bb/100)
          </span>
        </span>
      </div>
      <Table>
        <TableHeader>
          <TableRow className="text-[12px] uppercase tracking-wide">
            <TableHead className="py-1 px-2 h-auto">Hero Position</TableHead>
            <TableHead className="py-1 px-2 h-auto text-right">Hands</TableHead>
            <TableHead className="py-1 px-2 h-auto text-right">Won BB</TableHead>
            <TableHead className="py-1 px-2 h-auto text-right">bb/100</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.rows.map((r) => (
            <TableRow key={r.hero_position} className="text-[13px]">
              <TableCell className="py-1 px-2 font-mono">{r.hero_position}</TableCell>
              <TableCell className="py-1 px-2 text-right font-mono text-text-muted">{r.hands}</TableCell>
              <TableCell className={`py-1 px-2 text-right font-mono ${r.hero_won_bb >= 0 ? 'text-green' : 'text-red'}`}>
                {r.hero_won_bb >= 0 ? '+' : ''}{r.hero_won_bb.toFixed(1)}
              </TableCell>
              <TableCell className={`py-1 px-2 text-right font-mono ${r.bb_per_100 >= 0 ? 'text-green' : 'text-red'}`}>
                {r.bb_per_100.toFixed(1)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

const COLOR_OPTIONS = [
  { value: '', label: 'None', bg: 'bg-zinc-700' },
  { value: 'red', label: 'Red', bg: 'bg-red-500' },
  { value: 'orange', label: 'Orange', bg: 'bg-orange-500' },
  { value: 'green', label: 'Green', bg: 'bg-emerald-500' },
  { value: 'blue', label: 'Blue', bg: 'bg-blue-500' },
  { value: 'purple', label: 'Purple', bg: 'bg-purple-500' },
];

function NotesTab({ playerId, initialNotes, initialColor }: {
  playerId: number;
  initialNotes: string | null;
  initialColor: string | null;
}) {
  const queryClient = useQueryClient();
  const [notes, setNotes] = useState(initialNotes || '');
  const [colorTag, setColorTag] = useState(initialColor || '');

  const mutation = useMutation({
    mutationFn: (data: { notes?: string; color_tag?: string }) => updatePlayerNotes(playerId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.players.detail(playerId) });
    },
  });

  const handleSave = () => {
    mutation.mutate({ notes, color_tag: colorTag || '' });
  };

  const isDirty = notes !== (initialNotes || '') || colorTag !== (initialColor || '');

  return (
    <div className="max-w-lg space-y-4">
      <div>
        <div className="text-[12px] uppercase tracking-wider text-text-muted mb-2">Color Tag</div>
        <div className="flex items-center gap-2">
          {COLOR_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setColorTag(opt.value)}
              className={`w-7 h-7 rounded-full ${opt.bg} transition-all ${
                colorTag === opt.value ? 'ring-2 ring-primary ring-offset-2 ring-offset-background' : 'opacity-60 hover:opacity-100'
              }`}
              title={opt.label}
            />
          ))}
        </div>
      </div>
      <div>
        <div className="text-[12px] uppercase tracking-wider text-text-muted mb-2">Notes</div>
        <Textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={6}
          placeholder="Add notes about this player..."
          className="text-[13px] resize-y"
        />
      </div>
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          onClick={handleSave}
          disabled={mutation.isPending || !isDirty}
        >
          {mutation.isPending ? 'Saving...' : 'Save'}
        </Button>
        {mutation.isSuccess && !isDirty && (
          <span className="text-[12px] text-green">Saved</span>
        )}
      </div>
    </div>
  );
}

const TABS = ['Stats', 'Head-to-Head', 'Hands', 'Notes'] as const;
type Tab = typeof TABS[number];

export default function PlayerProfilePage() {
  const { playerId } = useParams<{ playerId: string }>();
  const pid = Number(playerId);
  const [activeTab, setActiveTab] = useState<Tab>('Stats');

  const { data: player, isPending: playerLoading, isError: playerError } = useQuery({
    queryKey: queryKeys.players.detail(pid),
    queryFn: () => getPlayer(pid),
    enabled: !isNaN(pid),
  });

  const { data: stats, isPending: statsLoading } = useQuery({
    queryKey: queryKeys.players.stats(pid, {}),
    queryFn: () => getPlayerStats(pid),
    enabled: !isNaN(pid) && activeTab === 'Stats',
  });

  if (playerLoading) {
    return <p className="text-text-muted text-sm py-8 text-center">Loading player...</p>;
  }

  if (playerError || !player) {
    return <p className="text-red text-sm py-8 text-center">Player not found</p>;
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-4">
        <div className="flex items-center gap-3 mb-1">
          <h1 className="text-xl font-bold">{player.username}</h1>
          <PlayerTypeBadge type={player.player_type} />
        </div>
        <div className="text-[13px] text-text-muted flex items-center gap-3">
          <span>{player.hands.toLocaleString()} hands</span>
          {player.stakes.length > 0 && (
            <span>{player.stakes.join(', ')}</span>
          )}
          {player.first_seen && player.last_seen && (
            <span>
              {formatRelativeDate(player.first_seen)} — {formatRelativeDate(player.last_seen)}
            </span>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-border mb-4">
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-3 py-1.5 text-[13px] font-medium transition-colors border-b-2 -mb-px ${
              activeTab === tab
                ? 'border-primary text-primary'
                : 'border-transparent text-text-muted hover:text-text'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'Stats' && (
        statsLoading || !stats
          ? <p className="text-text-muted text-sm py-4">Loading stats...</p>
          : stats.hands === 0
            ? <p className="text-text-muted text-sm py-4">No data available for this player.</p>
            : <StatsTab stats={stats} />
      )}
      {activeTab === 'Head-to-Head' && (
        <H2HTab playerId={pid} />
      )}
      {activeTab === 'Hands' && (
        <HandExplorer
          fixedParams={{ player_id: pid }}
          defaultPerPage={25}
        />
      )}
      {activeTab === 'Notes' && (
        <NotesTab playerId={pid} initialNotes={player.notes} initialColor={player.color_tag} />
      )}
    </div>
  );
}
