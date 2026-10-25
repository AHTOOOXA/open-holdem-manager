import { useQuery } from '@tanstack/react-query';
import { Copy } from 'lucide-react';
import { handDetailQuery } from '@/components/hands/handDetailQuery';
import { handHistoryText } from '@/lib/hands/hand-plot';
import { copyHandHistory } from '@/components/hands/handListActions';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';

/** "Show Hand History": the hand's original text in monospace with a copy button. */
export default function HandHistoryDialog({ handId, playerId, onClose, onCloseAutoFocus }: {
  handId: string;
  playerId?: number;
  onClose: () => void;
  /** Radix focus-restore hook: the list focuses the row the dialog was opened from (the row menu is gone by then). */
  onCloseAutoFocus?: (event: Event) => void;
}) {
  const { data, isError } = useQuery(handDetailQuery(handId, playerId));
  const text = data ? handHistoryText(data) : null;
  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="sm:max-w-2xl" onCloseAutoFocus={onCloseAutoFocus}>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            Hand history
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label="Copy hand history"
              title="Copy hand history"
              disabled={text === null}
              onClick={() => void copyHandHistory(handId, playerId)}
            >
              <Copy />
            </Button>
          </DialogTitle>
          <DialogDescription className="font-mono text-xs">{handId}</DialogDescription>
        </DialogHeader>
        <pre className="max-h-[60vh] overflow-auto rounded-card border border-border bg-surface-sunken p-3 font-mono text-sm leading-relaxed whitespace-pre-wrap text-foreground">
          {isError ? 'Could not load the hand.' : !data ? 'Loading…' : (text ?? 'No hand history stored for this hand.')}
        </pre>
      </DialogContent>
    </Dialog>
  );
}
