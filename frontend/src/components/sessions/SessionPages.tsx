/**
 * The page chain of one selected session: page 0 is the session, a Tables / Players row opens the
 * next page. Remount (key) to reset to page 0 when another session is selected.
 */
import { useCallback, useMemo } from 'react';
import { ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { PageChain } from '@/components/page-chain/PageChain';
import SessionPage from './SessionPage';
import { usePageChain } from '@/lib/page-chain';
import {
  childScope, freshPageState, sessionScope, type PageScope, type SessionPageState, type SessionTab,
} from '@/lib/sessions/pages';
import { liveClock, sessionCaption } from '@/lib/sessions/format';
import type { SessionRow } from '@/lib/sessions/types';
import type { SplitRow } from '@/lib/reports/types';

export function CollapseButton({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const label = collapsed ? 'Show session list' : 'Hide session list';
  const Icon = collapsed ? ChevronRight : ChevronLeft;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button variant="ghost" size="icon-sm" aria-label={label} aria-expanded={!collapsed} onClick={onToggle} className="text-muted-foreground">
          <Icon aria-hidden />
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}

export function Page0Header({ session, collapsed, onToggleCollapsed, onRefresh, refreshing, numericDate }: {
  session: SessionRow | null;
  collapsed: boolean;
  onToggleCollapsed: () => void;
  onRefresh: () => void;
  refreshing: boolean;
  numericDate: boolean;
}) {
  return (
    <div className="flex items-center gap-2 pt-3 pr-4 pl-3">
      <CollapseButton collapsed={collapsed} onToggle={onToggleCollapsed} />
      {collapsed && (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon-sm" aria-label="Refresh" onClick={onRefresh} className="text-muted-foreground">
              <RefreshCw className={refreshing ? 'animate-spin' : undefined} aria-hidden />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Refresh</TooltipContent>
        </Tooltip>
      )}
      {session && (session.is_live ? (
        <>
          <Badge variant="destructive" className="rounded-control px-2 py-1 text-label font-semibold uppercase">
            <span aria-hidden className="size-1.5 rounded-pill bg-current" />
            Live
          </Badge>
          <span className="text-sm">{liveClock(session.start)}</span>
        </>
      ) : (
        <span className="text-sm">
          {sessionCaption(session.start, { numeric: numericDate, currentYear: new Date().getFullYear() })}
        </span>
      ))}
    </div>
  );
}

export default function SessionPages({ workspaceId, playerId, session, collapsed, onToggleCollapsed, onRefresh, refreshing, numericDate }: {
  workspaceId: number;
  /** The dashboard's player (undefined = the active hero). */
  playerId?: number;
  session: SessionRow;
  collapsed: boolean;
  onToggleCollapsed: () => void;
  onRefresh: () => void;
  refreshing: boolean;
  numericDate: boolean;
}) {
  const caption = sessionCaption(session.start, { numeric: numericDate, currentYear: new Date().getFullYear() });
  const { pages, open, close, setState, resize } = usePageChain<PageScope, SessionPageState>({
    title: caption,
    inherited: sessionScope(session),
    state: freshPageState(),
  });

  // Page 0 follows the live session row (its end moves); later pages keep what they inherited
  const filter = session.filter;
  const scope0 = useMemo<PageScope>(() => ({ kind: 'session', chain: [filter] }), [filter]);

  const openRow = useCallback((i: number, tab: Exclude<SessionTab, 'hands'>, row: SplitRow) => {
    const parent = pages[i];
    if (!parent || parent.state.selectedKey === row.key) return; // the selected row does nothing
    const scope = childScope(parent.inherited, tab, row);
    if (!scope) return;
    setState(i, { ...parent.state, selectedKey: row.key });
    open(i, { title: row.caption, inherited: scope, state: freshPageState() });
    // A reused slot keeps its old state: every new page starts on Hands
    setState(i + 1, freshPageState());
  }, [pages, open, setState]);

  const clearSelection = useCallback((k: number) => {
    const page = pages[k];
    if (page) setState(k, { ...page.state, selectedKey: null });
  }, [pages, setState]);

  return (
    <PageChain
      pages={pages}
      renderHeader0={() => (
        <Page0Header
          session={session}
          collapsed={collapsed}
          onToggleCollapsed={onToggleCollapsed}
          onRefresh={onRefresh}
          refreshing={refreshing}
          numericDate={numericDate}
        />
      )}
      renderPage={(page, i) => (
        <SessionPage
          workspaceId={workspaceId}
          defaultPlayerId={playerId}
          scope={i === 0 ? scope0 : page.inherited}
          state={page.state}
          onTab={(tab) => setState(i, { ...page.state, tab })}
          onOpenRow={(tab, row) => openRow(i, tab, row)}
        />
      )}
      onClose={close}
      onSelectionCleared={clearSelection}
      onResize={resize}
      className="min-h-0 min-w-0 flex-1 p-2"
    />
  );
}
