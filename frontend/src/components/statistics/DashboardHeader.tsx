/**
 * Header of a Statistics dashboard (statistics-dashboards spec §4, own implementation):
 * [» when the tree is collapsed] · player · date · stakes + mode · profile | N hands · Refresh
 * (only when stale) · gear. Every control edits the dashboard definition; the parent ignores a
 * change that leaves the definition as it is.
 */
import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Check, ChevronDown, ChevronsRight, CalendarRange, RefreshCw, Settings, UserRound } from 'lucide-react';
import PlayerDialog, { type PickedPlayer } from '@/components/reports/PlayerDialog';
import { Button } from '@/components/ui/button';
import { DatePicker } from '@/components/ui/date-picker';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { useFilterOptions } from '@/hooks/useFilterOptions';
import { getHeroes } from '@/lib/api';
import { formatHands } from '@/lib/format';
import { sessionPresets } from '@/lib/reports/steps';
import {
  DEFAULT_PROFILE_ID, PROFILE_IDS, dateButtonLabel, dateChoiceId, dateStepOf, modeOf, profileLabel, stakesOf,
  withDate, withMode, withPlayer, withProfile, withStakes, type GameMode,
} from '@/lib/statistics/definition';
import type { DashboardDefinition } from '@/lib/statistics/types';
import { cn } from '@/lib/utils';

const ALL = '__all__';
const CONTROL = 'h-button gap-1.5 px-3 font-normal';

export interface DashboardHeaderProps {
  workspaceId: number;
  definition: DashboardDefinition;
  onChange: (next: DashboardDefinition) => void;
  onPickStat: () => void;
  treeCollapsed: boolean;
  onExpandTree: () => void;
  player: { name: string | null; site: string | null } | null;
  hands: number | null;
  fetching: boolean;
  stale: boolean;
  onRefresh: () => void;
  onExport: (() => void) | null;
  canDelete: boolean;
  onDelete: () => void;
  onClone: () => void;
}

export default function DashboardHeader({
  workspaceId, definition, onChange, onPickStat, treeCollapsed, onExpandTree, player, hands, fetching, stale,
  onRefresh, onExport, canDelete, onDelete, onClone,
}: DashboardHeaderProps) {
  const [playerOpen, setPlayerOpen] = useState(false);
  const heroes = useQuery({ queryKey: ['heroes', workspaceId], queryFn: () => getHeroes(workspaceId), staleTime: 60_000 });
  const { data: filterOpts } = useFilterOptions();

  const pickPlayer = (p: PickedPlayer) => {
    const hero = heroes.data?.active;
    // The active hero again: follow "the hero" (no id), like a new dashboard
    const isHero = !!hero && hero.username === p.username && (hero.site === p.site || hero.site_name === p.site);
    onChange(withPlayer(definition, isHero ? null : p.id));
  };

  const stakes = stakesOf(definition);
  const mode = modeOf(definition);
  const stakesList = useMemo(() => {
    const all = filterOpts?.stakes ?? [];
    return stakes && !all.includes(stakes) ? [stakes, ...all] : all;
  }, [filterOpts, stakes]);
  const profile = profileLabel(definition.profile_id);

  return (
    <div className="flex shrink-0 items-center justify-between gap-4 border-b border-border px-4 py-2">
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        {treeCollapsed && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon-sm" className="text-muted-foreground hover:text-foreground" aria-label="Show dashboards" onClick={onExpandTree}>
                <ChevronsRight />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Show dashboards</TooltipContent>
          </Tooltip>
        )}

        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" className={cn(CONTROL, 'min-w-0 max-w-72')} onClick={() => setPlayerOpen(true)}>
              <UserRound className="text-muted-foreground" aria-hidden />
              {player?.name ? (
                <span className="truncate">
                  {player.name}
                  {player.site && <span className="text-muted-foreground">, {player.site}</span>}
                </span>
              ) : (
                <span className="text-muted-foreground">{fetching ? 'Loading…' : 'Select player'}</span>
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent>Switch Player</TooltipContent>
        </Tooltip>

        <DateFilter definition={definition} onChange={onChange} />

        <Select value={stakes ?? ALL} onValueChange={(v) => onChange(withStakes(definition, v === ALL ? null : v))}>
          <SelectTrigger size="sm" aria-label="Stakes" className="h-button">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All stakes</SelectItem>
            {stakesList.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
          </SelectContent>
        </Select>

        <Select value={mode ?? ALL} onValueChange={(v) => onChange(withMode(definition, v === ALL ? null : (v as GameMode)))}>
          <SelectTrigger size="sm" aria-label="Game mode" className="h-button">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All games</SelectItem>
            <SelectItem value="fast">Fast Fold</SelectItem>
            <SelectItem value="regular">Regular</SelectItem>
          </SelectContent>
        </Select>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className={cn(CONTROL, 'min-w-0 max-w-80')} aria-label={`Profile: ${profile}`}>
              <span className="truncate">{profile}</span>
              <ChevronDown className="text-muted-foreground" aria-hidden />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            <DropdownMenuItem onSelect={onPickStat}>Existing Stat…</DropdownMenuItem>
            <DropdownMenuSeparator />
            {PROFILE_IDS.map((id) => (
              <DropdownMenuItem key={id} onSelect={() => onChange(withProfile(definition, id))}>
                <Check className={cn(definition.profile_id === id ? 'opacity-100' : 'opacity-0')} aria-hidden />
                {id === DEFAULT_PROFILE_ID ? 'default' : id}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        {fetching && <RefreshCw className="size-3 animate-spin text-muted-foreground" aria-label="Updating" role="status" />}
        {hands != null && (
          <span className="text-sm text-muted-foreground" title={`${hands.toLocaleString()} hands`}>
            {formatHands(hands)} hands
          </span>
        )}
        {stale && !fetching && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon-sm" className="text-primary" aria-label="Refresh" onClick={onRefresh}>
                <RefreshCw />
              </Button>
            </TooltipTrigger>
            <TooltipContent>New hands since this was built: Refresh</TooltipContent>
          </Tooltip>
        )}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon-sm" className="text-muted-foreground hover:text-foreground" aria-label="Dashboard menu">
              <Settings />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onSelect={onRefresh}>Refresh</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem disabled={!onExport} onSelect={() => onExport?.()}>Export As Json…</DropdownMenuItem>
            <DropdownMenuSeparator />
            {canDelete && <DropdownMenuItem onSelect={onDelete}>Delete Dashboard</DropdownMenuItem>}
            <DropdownMenuItem onSelect={onClone}>Clone Dashboard</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <PlayerDialog open={playerOpen} onOpenChange={setPlayerOpen} onSelect={pickPlayer} />
    </div>
  );
}

/** Date button: All Time, the relative presets (kept relative), or a custom range. */
function DateFilter({ definition, onChange }: { definition: DashboardDefinition; onChange: (d: DashboardDefinition) => void }) {
  const [open, setOpen] = useState(false);
  const current = dateChoiceId(definition);
  const step = dateStepOf(definition);
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const presets = sessionPresets().filter((p) => p.from);

  const openChange = (o: boolean) => {
    setOpen(o);
    if (o) {
      // The custom fields start from the current range
      setFrom(step?.from ?? '');
      setTo(step?.to ?? '');
    }
  };
  const pick = (d: DashboardDefinition) => {
    setOpen(false);
    onChange(d);
  };

  return (
    <Popover open={open} onOpenChange={openChange}>
      <PopoverTrigger asChild>
        <Button variant="ghost" className={CONTROL} aria-label={`Date: ${dateButtonLabel(definition)}`}>
          <CalendarRange className="text-muted-foreground" aria-hidden />
          {dateButtonLabel(definition)}
          <ChevronDown className="text-muted-foreground" aria-hidden />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-72 p-2">
        <div role="listbox" aria-label="Date range" className="flex flex-col">
          <DateOption label="All Time" on={current === 'all'} onPick={() => pick(withDate(definition, { kind: 'all' }))} />
          {presets.map((p) => (
            <DateOption key={p.id} label={p.label} on={current === p.id} onPick={() => pick(withDate(definition, { kind: 'preset', preset: p }))} />
          ))}
        </div>
        <Separator className="my-2" />
        <div className="flex flex-col gap-2 px-1 pb-1">
          <span className="text-label text-muted-foreground">Custom range{current === 'custom' ? ' (current)' : ''}</span>
          <div className="flex items-center gap-1.5">
            <DatePicker value={from} placeholder="From" onChange={setFrom} className="h-control flex-1 px-2" />
            <span className="text-muted-foreground" aria-hidden>–</span>
            <DatePicker value={to} placeholder="To" onChange={setTo} className="h-control flex-1 px-2" />
          </div>
          <Button
            size="sm"
            disabled={!from && !to}
            onClick={() => pick(withDate(definition, { kind: 'custom', from, to }))}
          >
            Apply
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}

function DateOption({ label, on, onPick }: { label: string; on: boolean; onPick: () => void }) {
  return (
    <Button
      variant="ghost"
      role="option"
      aria-selected={on}
      onClick={onPick}
      className={cn('h-row justify-start gap-2 px-2 font-normal', on && 'bg-overlay-selected')}
    >
      <Check className={cn('size-3.5', on ? 'opacity-100' : 'opacity-0')} aria-hidden />
      {label}
    </Button>
  );
}
