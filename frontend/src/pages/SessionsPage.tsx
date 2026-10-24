/**
 * Sessions screen (/sessions, /sessions/:sessionIndex): Hand2Note-style dashboard in one card,
 * [session list][page 0][page 1…]. The route param is the id of the session to preselect (an id
 * that matches nothing, e.g. an old numeric index, selects the newest session).
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { useWorkspace } from '@/contexts/WorkspaceContext';
import { useDayStartHour } from '@/hooks/useDayStart';
import { useSessionsLive } from '@/hooks/useSessionsLive';
import PlayerDialog, { type PickedPlayer } from '@/components/reports/PlayerDialog';
import SessionNav from '@/components/sessions/SessionNav';
import SessionPages, { Page0Header } from '@/components/sessions/SessionPages';
import { getHeroes } from '@/lib/api';
import { PLAYER_GONE_MESSAGE, isPlayerNotFound } from '@/lib/api-error';
import { APP_SETTINGS_DEFAULTS, appSettingsQueryKey, getAppSettings, patchAppSettings, type AppSettings } from '@/lib/app-settings';
import { reportKeys } from '@/lib/reports/query-keys';
import { getSessions, sessionsQueryKey } from '@/lib/sessions/api';
import {
  dateStorageKey, parseDateFilter, resolveDateFilter, serializeDateFilter, type StoredDateFilter,
} from '@/lib/sessions/date-filter';
import { parseSessionParam, pickSession } from '@/lib/sessions/pages';
import type { SessionsQuery } from '@/lib/sessions/types';

const COLLAPSED_KEY = 'ohm.sessions.collapsed';
const playerStorageKey = (workspaceId: number) => `ohm.sessions.player.${workspaceId}`;

function readStorage(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // storage unavailable: the screen still works, it just won't be restored
  }
}

function readPlayer(workspaceId: number): PickedPlayer | null {
  try {
    const v = JSON.parse(readStorage(playerStorageKey(workspaceId)) ?? 'null') as Partial<PickedPlayer> | null;
    return v && typeof v.id === 'number' && typeof v.username === 'string' && typeof v.site === 'string'
      ? { id: v.id, username: v.username, site: v.site }
      : null;
  } catch {
    return null;
  }
}

function SessionsDashboard({ workspaceId, paramId }: { workspaceId: number; paramId: number | null }) {
  const queryClient = useQueryClient();
  const settingsQuery = useQuery({ queryKey: appSettingsQueryKey, queryFn: getAppSettings });
  const settings: AppSettings = settingsQuery.data ?? APP_SETTINGS_DEFAULTS;
  useDayStartHour(); // keeps the preset default in sync for the report pages

  const [player, setPlayer] = useState<PickedPlayer | null>(() => readPlayer(workspaceId));
  const [playerOpen, setPlayerOpen] = useState(false);
  const [dateFilter, setDateFilter] = useState<StoredDateFilter>(() => parseDateFilter(readStorage(dateStorageKey(workspaceId))));
  const [collapsed, setCollapsed] = useState(() => readStorage(COLLAPSED_KEY) === '1');

  // Preselection: the route param, then whatever the user clicked; null = the newest session
  const [selectedId, setSelectedId] = useState<number | null>(paramId);
  const [seenParam, setSeenParam] = useState(paramId);
  if (paramId !== seenParam) {
    setSeenParam(paramId);
    setSelectedId(paramId);
  }

  const heroes = useQuery({ queryKey: ['heroes', workspaceId], queryFn: () => getHeroes(workspaceId) });
  const hero = heroes.data?.active ?? null;

  const bounds = resolveDateFilter(dateFilter, new Date(), settings.day_start_hour);
  const query: SessionsQuery = {
    workspace_id: workspaceId,
    ...(player ? { player_id: player.id } : {}),
    ...(bounds.date_from ? { date_from: bounds.date_from } : {}),
    ...(bounds.date_to ? { date_to: bounds.date_to } : {}),
  };
  const list = useQuery({
    queryKey: sessionsQueryKey(query),
    queryFn: ({ signal }) => getSessions(query, signal),
  });
  useSessionsLive(workspaceId, true);

  // A stored player that is gone from this database: back to the hero
  const playerGone = player != null && isPlayerNotFound(list.error);
  useEffect(() => {
    if (!playerGone) return;
    toast.error(PLAYER_GONE_MESSAGE);
    writeStorage(playerStorageKey(workspaceId), null);
  }, [playerGone, workspaceId]);
  if (playerGone) {
    setPlayer(null);
    setSelectedId(null);
  }

  const rows = list.data?.sessions;
  const session = useMemo(() => pickSession(rows ?? [], selectedId), [rows, selectedId]);

  const numeric = useMutation({
    mutationFn: (v: boolean) => patchAppSettings({ numeric_date_format: v }),
    onSuccess: (next) => queryClient.setQueryData(appSettingsQueryKey, next),
  });

  const refresh = useCallback(() => {
    setSelectedId(null); // the newest session is re-selected
    void queryClient.invalidateQueries({ queryKey: ['sessions'] });
    void queryClient.invalidateQueries({ queryKey: reportKeys.all });
    void queryClient.invalidateQueries({ queryKey: ['hands', 'list'] });
    void queryClient.invalidateQueries({ queryKey: ['graph'] });
  }, [queryClient]);
  const refreshing = list.isFetching && !list.isPending;

  const changeDate = (next: StoredDateFilter) => {
    setDateFilter(next);
    writeStorage(dateStorageKey(workspaceId), serializeDateFilter(next));
    setSelectedId(null);
  };

  const toggleCollapsed = () => {
    const next = !collapsed;
    setCollapsed(next);
    writeStorage(COLLAPSED_KEY, next ? '1' : '0');
  };

  const pickPlayer = (p: PickedPlayer) => {
    setPlayerOpen(false);
    // The active hero again: report on "the hero" (no player id), like a fresh dashboard
    const isHero = !!hero && hero.username === p.username && (hero.site === p.site || hero.site_name === p.site);
    const next = isHero ? null : p;
    if ((next?.id ?? null) === (player?.id ?? null)) return;
    setPlayer(next);
    writeStorage(playerStorageKey(workspaceId), next ? JSON.stringify(next) : null);
    setSelectedId(null);
  };

  const playerName = list.data?.player?.username ?? player?.username ?? hero?.username ?? null;
  const numericDate = settings.numeric_date_format;

  return (
    <div className="flex h-full min-h-0 flex-col pb-4">
      <div className="flex min-h-0 flex-1 overflow-hidden rounded-card border border-border bg-card">
        {!collapsed && (
          <SessionNav
            rows={rows}
            summary={list.data?.summary}
            loading={list.isFetching}
            error={list.isError ? list.error.message : null}
            selectedId={session?.id ?? null}
            onSelect={setSelectedId}
            onRefresh={refresh}
            refreshing={refreshing}
            playerName={playerName}
            onSwitchPlayer={() => setPlayerOpen(true)}
            dateFilter={dateFilter}
            onDateFilter={changeDate}
            dayStartHour={settings.day_start_hour}
            numericDate={numericDate}
            onNumericDate={(v) => numeric.mutate(v)}
          />
        )}
        <div className="flex min-w-0 flex-1 flex-col">
          {list.isPending ? (
            <div role="status" aria-label="Loading sessions" className="flex flex-1 items-center justify-center">
              <Loader2 className="size-6 animate-spin text-muted-foreground" aria-hidden />
            </div>
          ) : session ? (
            <SessionPages
              key={`${session.id}:${player?.id ?? 0}`}
              workspaceId={workspaceId}
              playerId={player?.id}
              session={session}
              collapsed={collapsed}
              onToggleCollapsed={toggleCollapsed}
              onRefresh={refresh}
              refreshing={refreshing}
              numericDate={numericDate}
            />
          ) : (
            <>
              <Page0Header
                session={null}
                collapsed={collapsed}
                onToggleCollapsed={toggleCollapsed}
                onRefresh={refresh}
                refreshing={refreshing}
                numericDate={numericDate}
              />
              <p className="p-6 text-sm text-muted-foreground">
                {list.isError ? 'Sessions could not be loaded.' : 'No results yet'}
              </p>
            </>
          )}
        </div>
      </div>
      <PlayerDialog open={playerOpen} onOpenChange={setPlayerOpen} onSelect={pickPlayer} />
    </div>
  );
}

export default function SessionsPage() {
  const { activeWorkspaceId } = useWorkspace();
  const { sessionIndex } = useParams<{ sessionIndex?: string }>();
  return (
    <SessionsDashboard
      key={activeWorkspaceId}
      workspaceId={activeWorkspaceId}
      paramId={parseSessionParam(sessionIndex)}
    />
  );
}
