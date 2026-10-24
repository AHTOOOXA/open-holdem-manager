/**
 * The workspace's dashboard tree document: loaded once, edited optimistically, saved whole.
 *
 * Every change writes the new document into the query cache at once and PUTs it. Saves are
 * serialised and coalesced (only the latest pending document is sent after the one in flight),
 * so a burst of edits can't land out of order. A failed save shows a toast and refetches the
 * stored document. Undo / redo keep a stack of tree structures for the session (lib/statistics/tree).
 */
import { useCallback, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { dashboardsQueryKey, getDashboards, putDashboards } from '@/lib/statistics/api';
import type { DashboardsDoc } from '@/lib/statistics/types';
import { forgetNodes } from '@/lib/statistics/pages';
import { EMPTY_HISTORY, removedNodeIds, pushHistory, redo as redoDoc, undo as undoDoc, type History } from '@/lib/statistics/tree';

export interface DashboardsDocApi {
  doc: DashboardsDoc | undefined;
  isPending: boolean;
  error: Error | null;
  refetch: () => void;
  /** Save `next` (no-op when it is the current document). `undoable` records the structure before it. */
  commit: (next: DashboardsDoc, opts?: { undoable?: boolean }) => void;
  canUndo: boolean;
  canRedo: boolean;
  undo: () => void;
  redo: () => void;
}

export function useDashboardsDoc(workspaceId: number): DashboardsDocApi {
  const qc = useQueryClient();
  const key = dashboardsQueryKey(workspaceId);
  const [history, setHistory] = useState<History>(EMPTY_HISTORY);

  const pending = useRef<DashboardsDoc | null>(null);
  const inFlight = useRef(false);
  const q = useQuery({
    queryKey: key,
    queryFn: async () => {
      const fetched = await getDashboards(workspaceId);
      // A save is pending or in flight: the local document is newer than this response
      const local = qc.getQueryData<DashboardsDoc>(dashboardsQueryKey(workspaceId));
      if (local && (pending.current || inFlight.current)) return local;
      // The server document replaces the local one (restore, workspace switch): old undo steps no longer apply
      setHistory(EMPTY_HISTORY);
      return fetched;
    },
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });

  /** Send pending documents one at a time until none is left (a newer edit replaces an unsent one). */
  const flush = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    try {
      while (pending.current) {
        const doc = pending.current;
        pending.current = null;
        try {
          const saved = await putDashboards(workspaceId, doc);
          // A newer local edit wins over the echo of an older one
          if (!pending.current) qc.setQueryData(dashboardsQueryKey(workspaceId), saved);
        } catch (e) {
          toast.error(e instanceof Error ? e.message : 'Saving dashboards failed');
          pending.current = null;
          void qc.invalidateQueries({ queryKey: dashboardsQueryKey(workspaceId) });
        }
      }
    } finally {
      inFlight.current = false;
    }
  }, [qc, workspaceId]);

  const save = useCallback((next: DashboardsDoc) => {
    // A refetch in flight must not overwrite the optimistic document (no revert: keep the cache as is)
    const cur = qc.getQueryData<DashboardsDoc>(dashboardsQueryKey(workspaceId));
    if (cur) forgetNodes(workspaceId, removedNodeIds(cur.nodes, next.nodes));
    void qc.cancelQueries({ queryKey: dashboardsQueryKey(workspaceId) }, { revert: false });
    qc.setQueryData(dashboardsQueryKey(workspaceId), next);
    pending.current = next;
    void flush();
  }, [qc, workspaceId, flush]);

  const commit = useCallback((next: DashboardsDoc, opts?: { undoable?: boolean }) => {
    const cur = qc.getQueryData<DashboardsDoc>(dashboardsQueryKey(workspaceId));
    if (!cur || next === cur) return;
    if (opts?.undoable) setHistory((h) => pushHistory(h, cur.nodes));
    save(next);
  }, [qc, workspaceId, save]);

  const undo = useCallback(() => {
    const cur = qc.getQueryData<DashboardsDoc>(dashboardsQueryKey(workspaceId));
    if (!cur) return;
    const r = undoDoc(history, cur);
    if (!r) return;
    setHistory(r.history);
    save(r.doc);
  }, [qc, workspaceId, history, save]);

  const redo = useCallback(() => {
    const cur = qc.getQueryData<DashboardsDoc>(dashboardsQueryKey(workspaceId));
    if (!cur) return;
    const r = redoDoc(history, cur);
    if (!r) return;
    setHistory(r.history);
    save(r.doc);
  }, [qc, workspaceId, history, save]);

  return {
    doc: q.data,
    isPending: q.isPending,
    error: q.error,
    refetch: () => void q.refetch(),
    commit,
    canUndo: history.past.length > 0,
    canRedo: history.future.length > 0,
    undo,
    redo,
  };
}
