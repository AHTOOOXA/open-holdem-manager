/**
 * The Reports dashboard of one workspace: a PageChain of report pages, page 0's header (player,
 * hand count, gear menu), persistence of the chain in localStorage and the per-"opened from"
 * memory of lower tab lists. Pure state transitions live in lib/reports/pages.ts.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Settings, UserRound } from 'lucide-react';
import { PageChain } from '@/components/page-chain/PageChain';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import PlayerDialog from './PlayerDialog';
import ReportPageView, { type PageActions } from './ReportPageView';
import type { HandsInit } from './LowerReports';
import { getHeroes } from '@/lib/api';
import { chainParam, getSpot } from '@/lib/reports/api';
import { reportKeys } from '@/lib/reports/query-keys';
import { activeLegacyFilters, legacyFilterLabels } from '@/lib/reports/legacy-filters';
import { count } from '@/lib/format';
import {
  addLowerTab, applyLegacyTab, chainStorageKey, closeAllPages, closePagesFrom, freshChain,
  openFrom, parseStoredChain, parseTabMemory, removeLowerTab, removeOwnStep, reportQuery, resetPage0,
  serializeChain, setCellsSelection, setHvSelection, setLowerTab, setOwnSteps, setUpperTab, tabMemoryKey, upperChain,
  type Dashboard, type LowerTab, type ReportChain, type ReportPage, type StoredPlayer,
} from '@/lib/reports/pages';
import { setWidth } from '@/lib/page-chain';
import type { LegacyReportLink } from '@/lib/reports-tab';

function readStorage(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    // storage full or unavailable: the screen still works, it just won't be restored
  }
}

const readTabMemory = (from: LowerTab) => parseTabMemory(readStorage(tabMemoryKey(from)));
const writeTabMemory = (from: LowerTab, tabs: LowerTab[]) => writeStorage(tabMemoryKey(from), JSON.stringify(tabs));

interface DashState {
  chain: ReportChain;
  player: StoredPlayer | null;
}

function loadDash(workspaceId: number): DashState {
  const stored = parseStoredChain(readStorage(chainStorageKey(workspaceId)));
  return stored ?? { chain: freshChain(readTabMemory('hands')), player: null };
}

export interface LegacyArrival {
  link: LegacyReportLink;
  /** Bumped for every arrival so the same link can be applied twice. */
  rev: number;
}

export default function ReportsDashboard({ workspaceId, legacy }: { workspaceId: number; legacy: LegacyArrival | null }) {
  const queryClient = useQueryClient();
  const [dash, setDash] = useState<DashState>(() => loadDash(workspaceId));
  const [playerOpen, setPlayerOpen] = useState(false);

  // Old `?tab=` links: applied once per arrival (render-time state update, no effect needed)
  const [appliedRev, setAppliedRev] = useState(0);
  if (legacy && legacy.rev !== appliedRev) {
    setAppliedRev(legacy.rev);
    setDash((d) => ({ ...d, chain: applyLegacyTab(d.chain, legacy.link.tab) }));
  }

  useEffect(() => {
    writeStorage(chainStorageKey(workspaceId), serializeChain(dash.chain, dash.player));
  }, [workspaceId, dash]);

  const update = useCallback((fn: (c: ReportChain) => ReportChain) => {
    setDash((d) => {
      const chain = fn(d.chain);
      return chain === d.chain ? d : { ...d, chain };
    });
  }, []);

  const { chain, player } = dash;
  const dashboard = useMemo<Dashboard>(
    () => (player ? { workspaceId, playerId: player.id } : { workspaceId }),
    [workspaceId, player],
  );

  // ── Page 0 header data
  const heroes = useQuery({ queryKey: ['heroes', workspaceId], queryFn: () => getHeroes(workspaceId) });
  const hero = heroes.data?.active ?? null;
  // The hand count comes from page 0's own Stats request (`total_hands`, every hand of the
  // player): a filtered page 0 must not resolve the empty chain just for this number.
  const page0 = chain.pages[0];
  const totalQuery = useMemo(() => reportQuery(dashboard, page0 ? upperChain(page0) : []), [dashboard, page0]);
  const spot = useQuery({
    queryKey: reportKeys.spot(totalQuery),
    queryFn: ({ signal }) => getSpot(totalQuery, signal),
  });

  const pickPlayer = useCallback((p: StoredPlayer) => {
    setPlayerOpen(false);
    // The active hero again: report on "the hero" (no player id), like a fresh dashboard
    const isHero = !!hero && hero.username === p.username && (hero.site === p.site || hero.site_name === p.site);
    const next = isHero ? null : p;
    setDash((d) => {
      if ((d.player?.id ?? null) === (next?.id ?? null)) return d;
      return { player: next, chain: closeAllPages(d.chain) };
    });
  }, [hero]);

  const refresh = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: reportKeys.all });
    void queryClient.invalidateQueries({ queryKey: ['hands', 'list'] });
    void queryClient.invalidateQueries({ queryKey: ['graph'] });
  }, [queryClient]);

  // ── Per-page actions (page = the page as rendered; tab memory is written from its current state)
  const pageActions = useCallback((i: number, page: ReportPage): PageActions => ({
    setOwn: (steps) => update((c) => setOwnSteps(c, i, steps)),
    removeOwn: (k) => update((c) => removeOwnStep(c, i, k)),
    setCells: (cells) => update((c) => setCellsSelection(c, i, cells)),
    setHv: (v) => update((c) => setHvSelection(c, i, v)),
    setUpperTab: (t) => update((c) => setUpperTab(c, i, t)),
    setLowerTab: (t) => update((c) => setLowerTab(c, i, t)),
    addLowerTab: (type) => {
      const s = page.state;
      if (!s.lowerTabs.includes(type)) writeTabMemory(s.openedFrom, [...s.lowerTabs, type]);
      update((c) => addLowerTab(c, i, type));
    },
    removeLowerTab: (tab) => {
      const s = page.state;
      if (tab !== 'hands' && s.lowerTabs.includes(tab)) writeTabMemory(s.openedFrom, s.lowerTabs.filter((t) => t !== tab));
      update((c) => removeLowerTab(c, i, tab));
    },
    openRow: (tab, row) => {
      const remembered = readTabMemory(tab);
      update((c) => openFrom(c, i, {
        selected: { tab, key: row.key },
        filter: row.filter,
        title: row.caption,
        openTab: row.open_tab,
        remembered,
      }));
    },
    openStat: (step, title) => {
      const remembered = readTabMemory('hands');
      update((c) => openFrom(c, i, { selected: { tab: 'stats', key: chainParam([step]) }, filter: step, title, remembered }));
    },
  }), [update]);

  // A leak link's hidden filters live until the user dismisses the notice (or a new link arrives)
  const [dismissedRev, setDismissedRev] = useState(0);
  const handsInit = useMemo<HandsInit | undefined>(() => {
    const active = activeLegacyFilters(legacy?.link, legacy?.rev ?? 0, dismissedRev);
    if (!legacy || !active) return undefined;
    const { statFlags, position, statKey } = active;
    return {
      rev: legacy.rev,
      labels: legacyFilterLabels(active),
      initialFilters: { statFlags, position },
      fixedParams: statKey ? { stat_key: statKey } : undefined,
    };
  }, [legacy, dismissedRev]);

  const username = player?.username ?? hero?.username;
  const site = player?.site ?? hero?.site_name;

  const header0 = () => (
    <div className="flex items-center justify-between gap-3 pt-4 pr-4 pl-6">
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            onClick={() => setPlayerOpen(true)}
            className="inline-flex h-button min-w-0 items-center gap-1.5 rounded-control border border-border bg-overlay-hover px-3 text-sm outline-none hover:bg-overlay-selected focus-visible:ring-2 focus-visible:ring-ring"
          >
            <UserRound className="size-4 shrink-0 text-muted-foreground" aria-hidden />
            {username ? (
              <span className="truncate">
                {username}
                {site && <span className="text-muted-foreground">, {site}</span>}
              </span>
            ) : (
              <span className="text-muted-foreground">{heroes.isPending ? 'Loading…' : 'Select player'}</span>
            )}
          </button>
        </TooltipTrigger>
        <TooltipContent>Switch Player</TooltipContent>
      </Tooltip>
      <div className="flex shrink-0 items-center gap-1">
        {spot.data && (
          <span className="px-2 text-sm text-muted-foreground" title={`${spot.data.total_hands ?? spot.data.hands} hands`}>
            {count(spot.data.total_hands ?? spot.data.hands)} hands
          </span>
        )}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              aria-label="Report settings"
              className="inline-flex size-7 items-center justify-center rounded-control text-muted-foreground outline-none hover:bg-overlay-hover hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Settings className="size-4" aria-hidden />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onSelect={refresh}>Refresh</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={() => update(resetPage0)}>Reset Filter</DropdownMenuItem>
            <DropdownMenuItem disabled={chain.pages.length < 2} onSelect={() => update(closeAllPages)}>
              Close Pages
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );

  return (
    <>
      <PageChain
        pages={chain.pages}
        renderHeader0={header0}
        renderPage={(page, i) => (
          <ReportPageView
            page={page}
            dashboard={dashboard}
            actions={pageActions(i, page)}
            handsInit={i === 0 ? handsInit : undefined}
            onClearHandsInit={() => setDismissedRev(legacy?.rev ?? 0)}
          />
        )}
        // closePagesFrom also clears the left page's selection (PageChain's onSelectionCleared)
        onClose={(i) => update((c) => closePagesFrom(c, i))}
        onResize={(i, px) => update((c) => setWidth(c, i, px))}
        className="min-h-0 flex-1 pb-4"
      />
      <PlayerDialog open={playerOpen} onOpenChange={setPlayerOpen} onSelect={pickPlayer} />
    </>
  );
}
