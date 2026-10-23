// STUB: replaced by the filter dialog track at merge. No real logic here.
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import type { Step } from '@/lib/reports/types';

export default function FilterDialog({ open, onOpenChange, value, onApply, initialTab }: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  value: Step[];
  onApply: (steps: Step[]) => void;
  initialTab?: 'quick' | 'positions' | 'general' | 'session';
}) {
  void onApply;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>Filter</DialogTitle>
        <DialogDescription>
          Placeholder ({value.length} steps, tab {initialTab ?? 'quick'}).
        </DialogDescription>
      </DialogContent>
    </Dialog>
  );
}
