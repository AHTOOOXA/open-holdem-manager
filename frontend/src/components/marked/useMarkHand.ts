import { useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { useWorkspace } from '@/contexts/WorkspaceContext';
import { getTagDefs, markHand, tagDefsQueryKey, unmarkHand } from '@/lib/marked/api';
import { patchRow } from '@/lib/marked/logic';
import type { MarkState, TagDef } from '@/lib/marked/types';
import type { HandListResponse } from '@/lib/api';

const NO_TAGS: TagDef[] = [];

/** The tag catalogue (shared react-query cache; the configuration section invalidates the same key). */
export function useTagDefs(): TagDef[] {
  const { data } = useQuery({ queryKey: tagDefsQueryKey, queryFn: getTagDefs, staleTime: 30_000 });
  return data ?? NO_TAGS;
}

/**
 * Mark / tag / unmark one hand. Updates cached hand-list rows right away, then refetches the
 * lists (and the General hands pane) so ordering and counts catch up.
 */
export function useMarkHand() {
  const qc = useQueryClient();
  const { activeWorkspaceId } = useWorkspace();

  const apply = useCallback(
    (state: Pick<MarkState, 'hand_id' | 'marked' | 'tags'>) => {
      qc.setQueriesData<HandListResponse>({ queryKey: ['hands', 'list'] }, (old) =>
        old && Array.isArray(old.hands) ? { ...old, hands: patchRow(old.hands, state) } : old,
      );
    },
    [qc],
  );
  const refresh = useCallback(() => {
    qc.invalidateQueries({ queryKey: ['hands'] });
    qc.invalidateQueries({ queryKey: ['general', 'hands'] });
  }, [qc]);

  /** Mark (no tag_ids) or set the full tag list (tag_ids replaces; an empty list keeps the hand marked). */
  const mark = useCallback(
    async (handId: string, tagIds?: number[]): Promise<MarkState | null> => {
      try {
        const state = await markHand(activeWorkspaceId, handId, tagIds ? { tag_ids: tagIds } : {});
        apply(state);
        refresh();
        return state;
      } catch (e) {
        toast.error('Could not mark the hand', { description: e instanceof Error ? e.message : undefined });
        return null;
      }
    },
    [activeWorkspaceId, apply, refresh],
  );
  const unmark = useCallback(
    async (handId: string): Promise<boolean> => {
      try {
        await unmarkHand(activeWorkspaceId, handId);
        apply({ hand_id: handId, marked: false, tags: [] });
        refresh();
        return true;
      } catch (e) {
        toast.error('Could not unmark the hand', { description: e instanceof Error ? e.message : undefined });
        return false;
      }
    },
    [activeWorkspaceId, apply, refresh],
  );
  return { mark, unmark };
}
