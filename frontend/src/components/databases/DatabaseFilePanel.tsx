import { useRef, useState } from 'react';
import { Download, RefreshCw, Trash2, Upload } from 'lucide-react';
import { useImport } from '@/contexts/ImportContext';
import { useWorkspace } from '@/contexts/WorkspaceContext';
import { toast } from 'sonner';
import { BUSY_TITLE } from '@/lib/import-ui';
import { Button } from '@/components/ui/button';
import ConfirmDialog from './ConfirmDialog';

type Pending =
  | { kind: 'restore'; file: File }
  | { kind: 'rebuild' }
  | { kind: 'clear' }
  | null;

/** Where the data lives and the whole-database actions (backup, restore, rebuild, clear). */
export default function DatabaseFilePanel() {
  const { phase, startRebuild, clearDb, exportDatabase, importDatabase } = useImport();
  const { activeWorkspace, totalHands } = useWorkspace();
  const fileRef = useRef<HTMLInputElement>(null);
  const [pending, setPending] = useState<Pending>(null);
  const busy = phase !== 'idle';
  const hasAnyHands = totalHands > 0;
  const activeHasHands = (activeWorkspace?.hand_count ?? 0) > 0;
  const busyTitle = busy ? BUSY_TITLE : undefined;

  const errText = (e: unknown, fallback: string) => (e instanceof Error && e.message ? e.message : fallback);

  const confirmPending = async () => {
    const p = pending;
    setPending(null);
    if (!p) return;
    try {
      if (p.kind === 'restore') {
        await importDatabase(p.file);
        toast.success('Database restored');
      } else if (p.kind === 'rebuild') {
        startRebuild();
      } else {
        await clearDb();
        toast.success('Hands cleared');
      }
    } catch (e) {
      toast.error(p.kind === 'restore' ? 'Restore failed' : 'Clearing hands failed', {
        description: errText(e, 'Unknown error'),
      });
    }
  };

  const runBackup = async () => {
    try {
      await exportDatabase();
    } catch (e) {
      toast.error('Backup failed', { description: errText(e, 'Unknown error') });
    }
  };

  const copy = {
    restore: {
      title: 'Restore from backup',
      description: pending?.kind === 'restore'
        ? `Restoring "${pending.file.name}" replaces all workspaces and hands. A copy of the current database is saved as poker.duckdb.bak.`
        : '',
      confirmLabel: 'Restore',
    },
    rebuild: {
      title: 'Rebuild statistics',
      description: `Rebuild all stats for ${totalHands.toLocaleString()} stored hands? This re-parses everything with the latest parser.`,
      confirmLabel: 'Rebuild',
    },
    clear: {
      title: 'Clear hands in this workspace',
      description: `Clear all hands from ${activeWorkspace?.name ?? 'this workspace'}? This cannot be undone.`,
      confirmLabel: 'Clear hands',
    },
  };

  return (
    <section aria-labelledby="db-file-heading" className="rounded-card border border-border bg-card">
      <div className="border-b border-border-subtle px-4 py-3">
        <h2 id="db-file-heading" className="text-sm font-semibold">Database file</h2>
        <p className="text-xs text-muted-foreground">Stored on this computer. Nothing is uploaded.</p>
      </div>
      <div className="flex flex-wrap gap-2 p-4">
        <Button variant="outline" size="sm" disabled={!hasAnyHands || busy} title={busyTitle} onClick={() => void runBackup()}>
          <Download className="size-3.5" />
          Back up database
        </Button>
        <Button variant="outline" size="sm" disabled={busy} title={busyTitle} onClick={() => fileRef.current?.click()}>
          <Upload className="size-3.5" />
          Restore from backup…
        </Button>
        <Button variant="outline" size="sm" disabled={!hasAnyHands || busy} title={busyTitle} onClick={() => setPending({ kind: 'rebuild' })}>
          <RefreshCw className="size-3.5" />
          Rebuild statistics…
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="text-destructive hover:text-destructive"
          disabled={busy || !activeHasHands}
          title={busyTitle}
          onClick={() => setPending({ kind: 'clear' })}
        >
          <Trash2 className="size-3.5" />
          Clear hands in this workspace…
        </Button>
      </div>
      <input
        ref={fileRef}
        type="file"
        accept=".duckdb"
        className="hidden"
        aria-label="Backup file"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) setPending({ kind: 'restore', file });
          e.target.value = '';
        }}
      />
      <ConfirmDialog
        open={pending !== null}
        title={pending ? copy[pending.kind].title : ''}
        description={pending ? copy[pending.kind].description : ''}
        confirmLabel={pending ? copy[pending.kind].confirmLabel : ''}
        destructive={pending?.kind !== 'rebuild'}
        requireText={pending?.kind === 'clear' ? (activeWorkspace?.name ?? '') : undefined}
        onConfirm={() => void confirmPending()}
        onCancel={() => setPending(null)}
      />
    </section>
  );
}
