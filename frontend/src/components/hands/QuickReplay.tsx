import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Pin, PinOff, Play } from 'lucide-react';
import { getHandDetail } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import {
  QUICK_REPLAY_CLOSE_GRACE_MS,
  QUICK_REPLAY_OPEN_MS,
  createHoverIntent,
} from '@/lib/hands/gestures';
import { Popover, PopoverAnchor, PopoverContent } from '@/components/ui/popover';
import { Button } from '@/components/ui/button';
import HandReplayer from '@/components/hands/replayer/HandReplayer';

/** Stop pointer / click events here so the popover (portaled, but React-wise inside the row) never selects or opens the row, or its menu. */
const stop = (e: { stopPropagation: () => void }) => e.stopPropagation();

function MiniReplayer({ handId, playerId }: { handId: string; playerId?: number }) {
  const { data, isError } = useQuery({
    queryKey: [...queryKeys.hands.detail(handId), playerId ?? null],
    queryFn: () => getHandDetail(handId, playerId),
    staleTime: 60_000,
  });
  if (isError) return <p className="text-sm text-muted-foreground">Could not load the hand.</p>;
  if (!data) return <p className="text-sm text-muted-foreground">Loading…</p>;
  return <HandReplayer hand={data} quick />;
}

/**
 * The round replay button of a hand row. Hover it for 300 ms (or focus it and press Enter) to open a mini
 * replayer that auto-plays one step every 300 ms; touching any control stops the play. It closes when the
 * pointer leaves button and popover, unless pinned.
 */
export default function QuickReplay({ handId, playerId }: { handId: string; playerId?: number }) {
  const [open, setOpen] = useState(false);
  const [pinned, setPinned] = useState(false);

  const [intent] = useState(() =>
    createHoverIntent({
      openDelay: QUICK_REPLAY_OPEN_MS,
      closeDelay: QUICK_REPLAY_CLOSE_GRACE_MS,
      onOpen: () => setOpen(true),
      onClose: () => setOpen(false),
    }),
  );
  useEffect(() => () => intent.dispose(), [intent]);

  const onOpenChange = (next: boolean) => {
    if (next) return;
    intent.notifyClosed();
    setPinned(false);
    setOpen(false);
  };

  return (
    <Popover open={open} onOpenChange={onOpenChange}>
      <PopoverAnchor asChild>
        <Button
          type="button"
          variant="outline"
          size="icon-xs"
          className="rounded-pill text-muted-foreground hover:text-primary"
          aria-label="Quick replay"
          title="Quick replay (hover, or Enter)"
          onPointerEnter={() => intent.enter()}
          onPointerLeave={() => intent.leave()}
          onClick={(e) => {
            e.stopPropagation();
            intent.openNow();
          }}
          onDoubleClick={stop}
          onContextMenu={stop}
        >
          <Play className="size-3 fill-current" />
        </Button>
      </PopoverAnchor>
      <PopoverContent
        side="right"
        align="start"
        className="w-105 p-3"
        onOpenAutoFocus={(e) => e.preventDefault()}
        onCloseAutoFocus={(e) => e.preventDefault()}
        onPointerEnter={() => intent.enter()}
        onPointerLeave={() => intent.leave()}
        onClick={stop}
        onDoubleClick={stop}
        onContextMenu={stop}
        onKeyDown={(e) => { if (e.key !== 'Escape') e.stopPropagation(); }}
      >
        <div className="mb-2 flex items-center justify-between">
          <span className="font-mono text-xs text-muted-foreground">{handId}</span>
          <Button
            type="button"
            variant="ghost"
            size="icon-xs"
            aria-label={pinned ? 'Unpin quick replay' : 'Pin quick replay'}
            aria-pressed={pinned}
            title={pinned ? 'Unpin' : 'Keep open'}
            className={pinned ? 'text-primary' : 'text-muted-foreground'}
            onClick={() => {
              intent.setPinned(!pinned);
              setPinned(!pinned);
            }}
          >
            {pinned ? <PinOff className="size-3.5" /> : <Pin className="size-3.5" />}
          </Button>
        </div>
        <MiniReplayer handId={handId} playerId={playerId} />
      </PopoverContent>
    </Popover>
  );
}
