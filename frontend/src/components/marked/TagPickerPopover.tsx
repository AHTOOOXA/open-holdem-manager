import { useState } from 'react';
import { Link } from 'react-router-dom';
import { X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Popover, PopoverAnchor, PopoverContent } from '@/components/ui/popover';
import { toggleId } from '@/lib/marked/logic';
import type { TagRef } from '@/lib/marked/types';
import TagCheckboxGrid from './TagCheckboxGrid';
import { useMarkHand, useTagDefs } from './useMarkHand';

interface Props {
  handId: string;
  /** Tags the hand carries when the picker opens. */
  initialTags: readonly TagRef[];
  onClose: () => void;
  /** Where the popover sits (client coordinates), or children as an anchor element. */
  point?: { x: number; y: number };
  children?: React.ReactNode;
}

/**
 * Tag picker for one hand. Every tick saves immediately: the first tick marks the hand, and
 * unticking the last tag leaves it marked. Render it only while open (state starts from the
 * hand's tags); `children` is the anchor, or pass `point`.
 */
export default function TagPickerPopover({ handId, initialTags, onClose, point, children }: Props) {
  const defs = useTagDefs();
  const { mark } = useMarkHand();
  const [ids, setIds] = useState<number[]>(() => initialTags.map((t) => t.id));
  const [busy, setBusy] = useState(false);

  const onToggle = async (id: number, on: boolean) => {
    const next = toggleId(ids, id, on);
    setIds(next);
    setBusy(true);
    const state = await mark(handId, next);
    setBusy(false);
    if (state) setIds(state.tags.map((t) => t.id));
    else setIds(ids);
  };

  return (
    <Popover open onOpenChange={(o) => { if (!o) onClose(); }}>
      {point ? (
        <PopoverAnchor asChild>
          <span aria-hidden className="pointer-events-none fixed size-px" style={{ left: point.x, top: point.y }} />
        </PopoverAnchor>
      ) : (
        <PopoverAnchor asChild>{children}</PopoverAnchor>
      )}
      <PopoverContent align="start" className="w-auto min-w-52 p-3">
        <div className="mb-2 flex items-center justify-between gap-4">
          <span className="text-label font-medium uppercase text-muted-foreground">Tags</span>
          <Button variant="ghost" size="icon-sm" aria-label="Close" onClick={onClose}>
            <X />
          </Button>
        </div>
        {defs.length === 0 ? (
          <p className="text-sm text-muted-foreground">No tags yet.</p>
        ) : (
          <TagCheckboxGrid tags={defs} selected={ids} onToggle={onToggle} disabled={busy} />
        )}
        <Link to="/configuration/tags" onClick={onClose} className="mt-2 block text-xs text-primary hover:underline">
          Manage tags…
        </Link>
      </PopoverContent>
    </Popover>
  );
}
