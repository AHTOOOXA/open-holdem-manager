import { useState } from 'react';
import { RotateCcw } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import ConfirmDialog from '@/components/databases/ConfirmDialog';

/** Section title, optional caption and optional "Reset to default" (confirm dialog first). */
export default function SectionHeader({ title, caption, onReset, resetDescription }: {
  title: string;
  caption?: string;
  /** Present = show the reset button. Rejecting shows an error toast. */
  onReset?: () => Promise<unknown>;
  resetDescription?: string;
}) {
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);

  const confirm = async () => {
    setAsking(false);
    setBusy(true);
    try {
      await onReset?.();
    } catch (e) {
      toast.error(`Couldn't reset ${title}`, { description: e instanceof Error ? e.message : undefined });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mb-4 flex items-start justify-between gap-3">
      <div className="min-w-0">
        <h2 className="text-base font-semibold">{title}</h2>
        {caption && <p className="mt-1 text-sm text-muted-foreground">{caption}</p>}
      </div>
      {onReset && (
        <>
          <Button variant="ghost" size="sm" className="shrink-0" disabled={busy} onClick={() => setAsking(true)}>
            <RotateCcw className="size-3.5" aria-hidden />
            Reset to default
          </Button>
          <ConfirmDialog
            open={asking}
            title={`Reset ${title}?`}
            description={resetDescription ?? 'The settings in this section go back to their defaults.'}
            confirmLabel="Reset"
            destructive
            onConfirm={() => void confirm()}
            onCancel={() => setAsking(false)}
          />
        </>
      )}
    </div>
  );
}
