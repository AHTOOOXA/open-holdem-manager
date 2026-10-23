// STUB: replaced by the player dialog track at merge. No real logic here.
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';

export default function PlayerDialog({ open, onOpenChange, onSelect }: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onSelect: (p: { id: number; username: string; site: string }) => void;
}) {
  void onSelect;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>Switch Player</DialogTitle>
        <DialogDescription>Placeholder.</DialogDescription>
      </DialogContent>
    </Dialog>
  );
}
