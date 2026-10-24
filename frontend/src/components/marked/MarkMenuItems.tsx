import { ContextMenuItem } from '@/components/ui/context-menu';
import { markMenuState } from '@/lib/marked/logic';
import { useMarkHand, useTagDefs } from './useMarkHand';

/**
 * Context-menu items for a hand row: Mark Hand / Mark Hand With Tags… / Unmark Hand.
 * `onPickTags` opens the tag picker for the hand (the host renders it).
 */
export default function MarkMenuItems({ handId, marked, onPickTags }: {
  handId: string;
  marked: boolean;
  onPickTags: (handId: string) => void;
}) {
  const { mark, unmark } = useMarkHand();
  const tagCount = useTagDefs().length;
  const s = markMenuState(marked, tagCount);
  return (
    <>
      {s.mark && <ContextMenuItem onSelect={() => void mark(handId)}>Mark Hand</ContextMenuItem>}
      {s.markWithTags && <ContextMenuItem onSelect={() => onPickTags(handId)}>Mark Hand With Tags…</ContextMenuItem>}
      {s.unmark && <ContextMenuItem onSelect={() => void unmark(handId)}>Unmark Hand</ContextMenuItem>}
    </>
  );
}
