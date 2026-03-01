import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getPlayer, getPlayerStats, getHeroStats, getHeadToHead, updatePlayerNotes } from '@/lib/api';
import type { HeroStats } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import PlayerTypeBadge from '@/components/PlayerTypeBadge';
import HandExplorer from '@/components/hands/HandExplorer';
import StatsCard from '@/components/stats/StatsCard';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { TooltipProvider } from '@/components/ui/tooltip';
import { formatRelativeDate } from '@/lib/utils';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

function StatsTab({ stats }: { stats: HeroStats }) {
  const [decimals, setDecimals] = useState<0 | 1>(0);

  const { data: heroStats } = useQuery({
    queryKey: queryKeys.stats.hero({}),
    queryFn: () => getHeroStats(),
  });

  const wr = stats.win_rate_bb100;
  const wrEv = stats.win_rate_ev_bb100;
  const wrColor = wr !== null ? (wr >= 0 ? 'text-green' : 'text-red') : 'text-text-muted';
  const wrEvColor = wrEv !== null ? (wrEv >= 0 ? 'text-green' : 'text-red') : 'text-text-muted';

  return (
    <TooltipProvider delayDuration={200}>
      <div className="space-y-2">
        <Card className="gap-0 py-0">
          <CardContent className="px-3 py-1.5 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-sm text-text-muted">{stats.hands.toLocaleString()} hands</span>
              <span className={`text-sm font-bold font-mono ${wrColor}`}>
                {wr !== null ? `${wr >= 0 ? '+' : ''}${wr.toFixed(2)} bb/100` : '\u2014'}
              </span>
              <span className={`text-sm font-bold font-mono ${wrEvColor}`}>
                EV {wrEv !== null ? `${wrEv >= 0 ? '+' : ''}${wrEv.toFixed(2)}` : '\u2014'}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-text-muted">Precision</span>
              <ToggleGroup
                type="single"
                value={String(decimals)}
                onValueChange={(v) => { if (v) setDecimals(Number(v) as 0 | 1); }}
                className="h-8"
              >
                <ToggleGroupItem value="0" className="h-7 px-2 text-xs font-mono">0</ToggleGroupItem>
                <ToggleGroupItem value="1" className="h-7 px-2 text-xs font-mono">0.0</ToggleGroupItem>
              </ToggleGroup>
            </div>
          </CardContent>
        </Card>
        <StatsCard stats={stats} decimals={decimals} compareStats={heroStats} />
      </div>
    </TooltipProvider>
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
