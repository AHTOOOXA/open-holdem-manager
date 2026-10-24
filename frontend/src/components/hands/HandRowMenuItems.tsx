import { ContextMenuItem, ContextMenuSeparator } from '@/components/ui/context-menu';
import MarkMenuItems from '@/components/marked/MarkMenuItems';
import { copyHandHistory } from '@/components/hands/handListActions';

/**
 * Context-menu items of a hand row, in the order every hand list uses: Open In Replayer, Show Hand Details,
 * Mark items, Copy / Show Hand History, and (lists that can export their filtered result) Export Hands….
 */
export default function HandRowMenuItems({
  handId,
  playerId,
  marked,
  onOpenReplayer,
  onShowDetails,
  onPickTags,
  onShowHistory,
  onExport,
}: {
  handId: string;
  playerId?: number;
  marked: boolean;
  onOpenReplayer: () => void;
  onShowDetails: () => void;
  onPickTags: (handId: string) => void;
  onShowHistory: () => void;
  onExport?: () => void;
}) {
  return (
    <>
      <ContextMenuItem onSelect={onOpenReplayer}>Open In Replayer</ContextMenuItem>
      <ContextMenuItem onSelect={onShowDetails}>Show Hand Details</ContextMenuItem>
      <ContextMenuSeparator />
      <MarkMenuItems handId={handId} playerId={playerId} marked={marked} onPickTags={onPickTags} />
      <ContextMenuSeparator />
      <ContextMenuItem onSelect={() => void copyHandHistory(handId, playerId)}>Copy Hand History</ContextMenuItem>
      <ContextMenuItem onSelect={onShowHistory}>Show Hand History</ContextMenuItem>
      {onExport && (
        <>
          <ContextMenuSeparator />
          <ContextMenuItem onSelect={onExport}>Export Hands…</ContextMenuItem>
        </>
      )}
    </>
  );
}
