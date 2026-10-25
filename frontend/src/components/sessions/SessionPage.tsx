/**
 * Body of one Sessions page: Stats block (recipe by page kind), the winnings graph (always
 * visible) and the fixed lower tabs (Hands / Tables / Players by page kind).
 */
import { lazy, Suspense, useMemo } from 'react';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { usePageLevel } from '@/components/page-chain/PageChain';
import HandExplorer from '@/components/hands/HandExplorer';
import SplitReport from '@/components/reports/SplitReport';
import { Skeleton } from '@/components/ui/skeleton';
import SessionStats from './SessionStats';
import type { ReportQuery, SplitRow } from '@/lib/reports/types';
import {
  isSessionTab, recipeFor, TAB_CAPTION, tabsFor, type PageScope, type SessionPageState, type SessionTab,
} from '@/lib/sessions/pages';
import { cn } from '@/lib/utils';

// The charting stack is the largest vendor chunk: the stats and hands render without waiting for it
const GraphTab = lazy(() => import('@/components/reports/tabs/GraphTab'));

const HANDS_GRID_MAX_HEIGHT = 'max(18rem, calc(100dvh - 22rem))';

export default function SessionPage({ workspaceId, defaultPlayerId, scope, state, onTab, onOpenRow }: {
  workspaceId: number;
  /** The dashboard's player (undefined = the active hero). */
  defaultPlayerId?: number;
  scope: PageScope;
  state: SessionPageState;
  onTab: (tab: SessionTab) => void;
  onOpenRow: (tab: Exclude<SessionTab, 'hands'>, row: SplitRow) => void;
}) {
  const { lower } = usePageLevel();
  const playerId = scope.playerId ?? defaultPlayerId;
  const query = useMemo<ReportQuery>(
    () => ({ workspace_id: workspaceId, player_id: playerId, chain: scope.chain }),
    [workspaceId, playerId, scope.chain],
  );
  const tabs = tabsFor(scope.kind);
  const tab = state.tab;

  return (
    <div className="flex min-w-0 flex-col gap-4 pt-1">
      <div className="px-6">
        <SessionStats query={query} recipe={recipeFor(scope.kind)} />
      </div>
      <div className="px-4">
        <Suspense fallback={<Skeleton className="m-2 h-80 w-auto rounded" aria-busy />}>
          <GraphTab query={query} />
        </Suspense>
      </div>
      <div className={cn('flex min-h-100 flex-1 flex-col gap-2 pt-2 pb-4', lower)}>
        <Tabs value={tab} onValueChange={(v) => { if (isSessionTab(v, scope.kind)) onTab(v); }} className="gap-0">
          <TabsList variant="line" aria-label="Session reports" className="border-b-0 pl-3">
            {tabs.map((t) => (
              <TabsTrigger key={t} value={t}>{TAB_CAPTION[t]}</TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <div className="min-w-0 px-3">
          {tab === 'hands' ? (
            <HandExplorer
              chain={query.chain}
              hideFilters
              fixedParams={query.player_id ? { player_id: query.player_id } : undefined}
              gridMaxHeight={HANDS_GRID_MAX_HEIGHT}
              emptyMessage="No results yet"
            />
          ) : (
            <SplitReport
              key={tab}
              type={tab}
              query={query}
              selectedKey={state.selectedKey}
              onOpenRow={(row) => onOpenRow(tab, row)}
            />
          )}
        </div>
      </div>
    </div>
  );
}
