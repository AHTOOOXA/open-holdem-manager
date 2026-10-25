import { useCallback, useSyncExternalStore } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { isOutdatedOnScreen, refetchOutdatedOnScreen } from '@/lib/query-policy';

/** Number of visible heavy queries that show data from before the last auto-import tick. */
function useOutdatedOnScreen(): number {
  const cache = useQueryClient().getQueryCache();
  const subscribe = useCallback((onChange: () => void) => cache.subscribe(onChange), [cache]);
  const snapshot = useCallback(() => cache.getAll().filter(isOutdatedOnScreen).length, [cache]);
  return useSyncExternalStore(subscribe, snapshot, snapshot);
}

/**
 * Caption-row chip while auto-import added hands that the visible report does not include yet.
 * Heavy screens are not recomputed on every tick (lib/query-policy.ts); Refresh recomputes them once.
 */
export default function NewHandsIndicator() {
  const qc = useQueryClient();
  const outdated = useOutdatedOnScreen();
  if (outdated === 0) return null;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="outline"
          size="xs"
          className="shrink-0 rounded-pill text-muted-foreground hover:text-foreground"
          onClick={() => void refetchOutdatedOnScreen(qc).catch(() => {})}
        >
          <RefreshCw aria-hidden />
          New hands
        </Button>
      </TooltipTrigger>
      <TooltipContent>Auto import added hands. Refresh this screen to include them.</TooltipContent>
    </Tooltip>
  );
}
