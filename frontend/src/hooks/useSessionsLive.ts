import { useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getSessionsLive, sessionsLiveQueryKey } from '@/lib/sessions/api';
import { LIVE_POLL_MS, liveFlipped, liveSignature } from '@/lib/sessions/live';

/**
 * Polls whether the hero's newest session is live (every 60 s). With `refetchListOnFlip` the
 * session list is refetched when the live state changes, so the list dot and page-0 pill follow.
 */
export function useSessionsLive(workspaceId: number, refetchListOnFlip = false) {
  const queryClient = useQueryClient();
  const q = useQuery({
    queryKey: sessionsLiveQueryKey(workspaceId),
    queryFn: ({ signal }) => getSessionsLive(workspaceId, signal),
    refetchInterval: LIVE_POLL_MS,
    refetchIntervalInBackground: false,
  });
  const signature = liveSignature(q.data);
  const prev = useRef<string | null>(null);
  useEffect(() => {
    if (refetchListOnFlip && liveFlipped(prev.current, signature)) {
      void queryClient.invalidateQueries({
        predicate: (query) => query.queryKey[0] === 'sessions' && query.queryKey[1] !== 'live',
      });
    }
    prev.current = signature;
  }, [signature, refetchListOnFlip, queryClient]);
  return q.data;
}
