import { useEffect, useState } from 'react';
import { AlertTriangle, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { getHealth, type HealthResponse } from '@/lib/api';

/**
 * Shown when the backend had to move a corrupt write-ahead log aside on startup
 * (e.g. after a crash or power cut). The database opened, but changes made
 * since the last checkpoint are gone, so the user should know to re-import.
 */
export default function DbRecoveryBanner() {
  const [recovery, setRecovery] = useState<HealthResponse['wal_recovery'] | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    getHealth()
      .then((h) => setRecovery(h.wal_recovery ?? null))
      .catch(() => {});
  }, []);

  if (!recovery || dismissed) return null;

  return (
    <div className="flex items-start gap-3 border-b border-border bg-surface px-4 py-2 text-xs">
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-red" />
      <div className="min-w-0 flex-1 text-muted-foreground">
        <span className="font-medium text-foreground">The database was recovered after an unclean shutdown.</span>{' '}
        Your most recent changes (for example, the last import) may be missing. Re-import those files to restore
        them. The unrecoverable log was kept at{' '}
        <span className="break-all font-mono">{recovery.quarantined_wal}</span>.
      </div>
      <Button variant="ghost" size="icon" className="size-6 shrink-0" onClick={() => setDismissed(true)} aria-label="Dismiss">
        <X className="size-3.5" />
      </Button>
    </div>
  );
}
