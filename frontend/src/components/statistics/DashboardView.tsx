/**
 * One Statistics dashboard: its header and its pages (statistics-dashboards spec §3, §5).
 *
 * Page 0 is the "default" profile (GENERAL grid + Notes) or, for a single-stat dashboard, the
 * stat detail. Clicks open pages to the right with the Statistics rule (lib/statistics/pages):
 * a click on page k closes everything after k and appends a new page. Pages and selections are
 * kept in memory per dashboard; any definition change starts over from page 0.
 *
 * Stale: results are cached per definition and not refetched when a dashboard is shown again
 * (instant tree switching). An import or rebuild invalidates every query; the shown dashboard
 * refetches right away, a cached one shown later keeps its numbers and offers Refresh
 * (`isStale` of the General query).
 */
import { useEffect, useMemo, useState } from 'react';
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query';
import { HEAVY_QUERY } from '@/lib/query-policy';
import { RefreshCw } from 'lucide-react';
import EmptyState from '@/components/EmptyState';
import GeneralGrid from '@/components/general/GeneralGrid';
import GeneralHandList from '@/components/general/GeneralHandList';
import StatPopup, { StatInfo } from '@/components/general/StatPopup';
import HandExplorer from '@/components/hands/HandExplorer';
import { PageChain } from '@/components/page-chain/PageChain';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import { PLAYER_GONE_MESSAGE, isPlayerNotFound } from '@/lib/api-error';
import { useDayKey } from '@/hooks/useDayStart';
import { useWorkspace } from '@/contexts/WorkspaceContext';
import { cellDetailQueryKey, generalQueryKey, getGeneral } from '@/lib/api-general';
import type { CellDetail, GeneralCell, GeneralResponse } from '@/lib/api-general';
import { GENERAL_CELLS, SUMMARY_CELL_IDS } from '@/lib/h2n-layout';
import type { Page } from '@/lib/page-chain';
import { setWidth } from '@/lib/page-chain';
import { stripUiFields } from '@/lib/reports/steps';
import { reportKeys } from '@/lib/reports/query-keys';
import {
  definitionKey, exportFileName, withPlayer, generalParams, resolvedDateRange, sameDefinition, singleStatMeta,
} from '@/lib/statistics/definition';
import {
  ROOT_PAGE_WIDTH, STAT_PAGE_WIDTH, cellHandsPage, closePages, freshStatChain, labelDetailChain,
  loadPages, nextActionHandsPage, openFromPage, pagesStoreKey, rangeHandsPage, savePages, selectOnly, statPage,
  type PageState, type StatChain, type StatPage, type StoredPages,
} from '@/lib/statistics/pages';
import type { DashboardLeaf } from '@/lib/statistics/tree';
import type { DashboardDefinition } from '@/lib/statistics/types';
import DashboardHeader from './DashboardHeader';
import ExistingStatDialog from './ExistingStatDialog';
import NotesTab from './NotesTab';

/** Hands and bb/100 also travel as top-level fields; make sure the grid sees them as cells. */
function cellsWithSummary(res: GeneralResponse): Record<string, GeneralCell> {
  const cells: Record<string, GeneralCell> = { ...res.cells };
  cells[SUMMARY_CELL_IDS.hands] ??= { value: res.hands, sample: null };
  cells[SUMMARY_CELL_IDS.bb100] ??= { value: res.bb100, sample: res.hands };
  return cells;
}

function downloadJson(data: unknown, filename: string) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** Line tab of page 0: muted, active in the foreground over the primary indicator. */
const PAGE_TAB =
  'flex-none rounded-none px-0 text-sm font-medium tracking-normal text-muted-foreground after:bg-primary hover:text-foreground data-[state=active]:text-foreground';

const LAST_PAGE_MIN = 560;
const HANDS_PAGE_MIN = 800;

export interface DashboardViewProps {
  workspaceId: number;
  dashboard: DashboardLeaf;
  onDefinitionChange: (next: DashboardDefinition) => void;
  treeCollapsed: boolean;
  onExpandTree: () => void;
  canDelete: boolean;
  onDelete: () => void;
  onClone: () => void;
}

export default function DashboardView({
  workspaceId, dashboard, onDefinitionChange, treeCollapsed, onExpandTree, canDelete, onDelete, onClone,
}: DashboardViewProps) {
  const qc = useQueryClient();
  const { activeWorkspace } = useWorkspace();
  const def = dashboard.definition;
  const defKey = definitionKey(def);
  const single = singleStatMeta(def.profile_id);
  const rootWidth = single ? STAT_PAGE_WIDTH : ROOT_PAGE_WIDTH;
  const dayKey = useDayKey(); // presets re-derive when the day (or the day-start hour) changes
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const params = useMemo(() => generalParams(def, workspaceId), [def, workspaceId, dayKey]);
  const [statDialog, setStatDialog] = useState(false);

  const general = useQuery({
    queryKey: generalQueryKey(params),
    queryFn: ({ signal }) => getGeneral(params, signal),
    placeholderData: keepPreviousData,
    staleTime: Infinity,
    // A valid cached grid costs no request; an invalidated one (data changed while away, or a
    // post-import refetch cancelled by leaving the screen) refetches once on return
    refetchOnMount: (q) => q.state.isInvalidated,
    refetchOnWindowFocus: false,
    ...HEAVY_QUERY,
  });
  const data = general.data;

  // A stored player that is gone from this database: save the dashboard back to the hero
  const playerGone = def.player_id != null && isPlayerNotFound(general.error);
  useEffect(() => {
    if (!playerGone) return;
    onDefinitionChange(withPlayer(def, null));
    toast.error(PLAYER_GONE_MESSAGE);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playerGone]);

  // ── Pages (in memory per dashboard; a new definition starts over)
  const storeKey = pagesStoreKey(workspaceId, dashboard.id);
  const [pages, setPages] = useState<StoredPages>(() => loadPages(storeKey, defKey, rootWidth));
  if (pages.defKey !== defKey) setPages({ defKey, chain: freshStatChain(rootWidth) });
  const update = (fn: (c: StatChain) => StatChain) => setPages((p) => {
    const chain = fn(p.chain);
    if (chain === p.chain) return p;
    const next = { ...p, chain };
    savePages(storeKey, next);
    return next;
  });
  const chain = pages.chain;

  const change = (next: DashboardDefinition) => {
    if (!sameDefinition(next, def)) onDefinitionChange(next);
  };

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ['general'] });
    void qc.invalidateQueries({ queryKey: reportKeys.all });
    void qc.invalidateQueries({ queryKey: ['hands', 'list'] });
  };

  const playerName = data?.player ?? (def.player_id == null ? activeWorkspace?.hero_username ?? null : null);
  const playerSite = data?.site ?? (def.player_id == null ? activeWorkspace?.hero_site ?? null : null);
  const playerId = def.player_id ?? data?.player_id ?? null;

  const exportJson = data ? () => {
    const stat = single ? qc.getQueryData<CellDetail>(cellDetailQueryKey(def.profile_id, params)) : undefined;
    downloadJson({
      dashboard: dashboard.name,
      player: { id: playerId, name: playerName, site: playerSite },
      date_range: resolvedDateRange(def),
      filters: stripUiFields(def.filters, false),
      profile_id: def.profile_id,
      hands: data.hands,
      bb100: data.bb100,
      cells: data.cells,
      ...(stat ? { stat } : {}),
    }, exportFileName(dashboard.name, playerName));
  } : null;

  // ── Page bodies
  const renderPage = (page: Page<StatPage, PageState>, i: number) => {
    const p = page.inherited;
    const sel = page.state.selection;
    const statBody = (cellId: string, isRoot: boolean) => {
      const meta = GENERAL_CELLS[cellId];
      if (!meta) return null;
      return (
        <StatPopup
          key={cellId}
          embedded
          hideTitle={!isRoot}
          cellId={cellId}
          meta={meta}
          params={params}
          selection={sel?.t === 'hands' ? sel.sel : null}
          onSelect={(s) => update((c) => openFromPage(c, i, { t: 'hands', sel: s }, cellHandsPage(cellId, s)))}
          rangeCells={sel?.t === 'range' ? sel.cells : []}
          onSelectRange={(cells, cellChain) => update((c) => (cells.length === 0
            ? selectOnly(c, i, null)
            : openFromPage(c, i, { t: 'range', cells }, rangeHandsPage(labelDetailChain(cellChain, meta), cells))))}
          nextKey={sel?.t === 'next' ? sel.key : null}
          onSelectNext={(row, cellChain) => update((c) => openFromPage(
            c, i, { t: 'next', key: row.key }, nextActionHandsPage(labelDetailChain(cellChain, meta), row),
          ))}
        />
      );
    };

    if (p.kind === 'root') {
      if (single) return statBody(single.id, true);
      return (
        <ProfilePage
          data={data}
          isPending={general.isPending}
          error={general.isError ? general.error : null}
          isPlaceholder={general.isPlaceholderData}
          onRetry={() => void general.refetch()}
          retrying={general.isFetching}
          playerName={playerName ?? 'No hero yet'}
          playerId={playerId}
          emptyHero={def.player_id == null && def.filters.length === 0}
          selectedCellId={sel?.t === 'cell' ? sel.id : null}
          onSelectCell={(id) => {
            const meta = GENERAL_CELLS[id];
            // Expression stats only highlight; the sample grid has no hands behind it
            if (meta?.kind === 'action' && !data?.mock) update((c) => openFromPage(c, i, { t: 'cell', id }, statPage(id)));
            else update((c) => selectOnly(c, i, { t: 'cell', id }));
          }}
        />
      );
    }
    if (p.kind === 'stat') return statBody(p.cellId, false);
    if (p.kind === 'cell_hands') {
      const { bucket, board, size } = p.selection;
      return (
        <div className="flex min-h-0 flex-1 flex-col pt-2">
          <GeneralHandList cellId={p.cellId} params={params} filter={{ bucket, board, size }} />
        </div>
      );
    }
    return (
      <div className="min-h-0 flex-1 overflow-y-auto px-3 pt-3 pb-4">
        <HandExplorer
          chain={p.chain}
          hideFilters
          fixedParams={def.player_id != null ? { player_id: def.player_id } : undefined}
          gridMaxHeight="calc(100dvh - 16rem)"
          emptyMessage="No results yet"
        />
      </div>
    );
  };

  const last = chain.pages[chain.pages.length - 1]?.inherited;
  const lastMin = last && (last.kind === 'cell_hands' || last.kind === 'chain_hands') ? HANDS_PAGE_MIN : LAST_PAGE_MIN;

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      <DashboardHeader
        workspaceId={workspaceId}
        definition={def}
        onChange={change}
        onPickStat={() => setStatDialog(true)}
        treeCollapsed={treeCollapsed}
        onExpandTree={onExpandTree}
        player={{ name: playerName, site: playerSite }}
        hands={data?.hands ?? null}
        fetching={general.isFetching}
        stale={general.isStale && !!data}
        onRefresh={refresh}
        onExport={exportJson}
        canDelete={canDelete}
        onDelete={onDelete}
        onClone={onClone}
      />
      <PageChain
        pages={chain.pages}
        renderPage={renderPage}
        onClose={(i) => update((c) => closePages(c, i))}
        onResize={(i, px) => update((c) => setWidth(c, i, px))}
        titleAddon={(page) => {
          const p = page.inherited;
          const meta = p.kind === 'stat' ? GENERAL_CELLS[p.cellId] : undefined;
          return meta && p.kind === 'stat' ? <StatInfo cellId={p.cellId} meta={meta} params={params} /> : null;
        }}
        lastPageMinWidth={lastMin}
        className="min-h-0 flex-1 p-3"
      />
      <ExistingStatDialog
        open={statDialog}
        onOpenChange={setStatDialog}
        currentId={single?.id ?? null}
        onPick={(id) => change({ ...def, profile_id: id })}
      />
    </div>
  );
}

// ── Page 0 of a profile dashboard ──────────────────────────────────────────────────────────

interface ProfilePageProps {
  data: GeneralResponse | undefined;
  isPending: boolean;
  error: Error | null;
  isPlaceholder: boolean;
  onRetry: () => void;
  retrying: boolean;
  playerName: string;
  playerId: number | null;
  /** No player and no filters: 0 hands means the hero has none at all (no-data state). */
  emptyHero: boolean;
  selectedCellId: string | null;
  onSelectCell: (id: string) => void;
}

function ProfilePage({
  data, isPending, error, isPlaceholder, onRetry, retrying, playerName, playerId, emptyHero, selectedCellId, onSelectCell,
}: ProfilePageProps) {
  const [tab, setTab] = useState('general');
  const cells = useMemo(() => (data ? cellsWithSummary(data) : {}), [data]);

  return (
    <Tabs value={tab} onValueChange={setTab} className="min-h-0 flex-1 gap-0">
      <TabsList variant="line" className="h-9 shrink-0 gap-4 px-4">
        <TabsTrigger value="general" className={PAGE_TAB}>GENERAL</TabsTrigger>
        {playerId != null && <TabsTrigger value="notes" className={PAGE_TAB}>Notes</TabsTrigger>}
        {data?.mock && (
          <Badge variant="outline" className="ml-auto self-center border-border text-muted-foreground" title="The stats endpoint is not available yet; showing sample numbers">
            Sample data
          </Badge>
        )}
      </TabsList>

      <TabsContent value="general" className="min-h-0 overflow-auto">
        <div className="py-4">
          {isPending ? (
            <p className="px-4 text-sm text-muted-foreground">Loading…</p>
          ) : error && !data ? (
            <div role="alert" className="flex flex-col items-start gap-3 px-4">
              <p className="text-sm text-foreground">Could not load statistics.</p>
              {error.message && <p className="text-sm text-muted-foreground">{error.message}</p>}
              <Button variant="outline" size="sm" onClick={onRetry} disabled={retrying}>
                <RefreshCw className={retrying ? 'animate-spin' : undefined} /> Retry
              </Button>
            </div>
          ) : !data ? null : data.hands === 0 && emptyHero && !data.mock ? (
            <EmptyState variant="no-data" />
          ) : (
            <div className="transition-opacity" style={{ opacity: isPlaceholder ? 0.6 : 1 }} aria-busy={isPlaceholder || undefined}>
              {error && (
                <div role="alert" className="mb-3 flex items-center gap-3 px-4 text-sm text-muted-foreground">
                  <span>Could not refresh statistics{error.message ? `: ${error.message}` : '.'}</span>
                  <Button variant="outline" size="sm" onClick={onRetry} disabled={retrying}>Retry</Button>
                </div>
              )}
              <GeneralGrid cells={cells} playerName={playerName} selectedCellId={selectedCellId} onSelectCell={onSelectCell} />
            </div>
          )}
        </div>
      </TabsContent>
      {playerId != null && (
        <TabsContent value="notes" className="min-h-0 overflow-y-auto px-4 pt-4 pb-4">
          <NotesTab playerId={playerId} />
        </TabsContent>
      )}
    </Tabs>
  );
}

