import { useRef, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import {
  DatabaseBackup,
  ExternalLink,
  FileInput,
  FolderInput,
  FolderUp,
  Info,
  Layers,
  RefreshCw,
  RotateCw,
  Sparkles,
  Trash2,
  XCircle,
} from 'lucide-react';
import {
  Menubar,
  MenubarContent,
  MenubarItem,
  MenubarMenu,
  MenubarSeparator,
  MenubarTrigger,
} from '@/components/ui/menubar';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useImport } from '@/contexts/ImportContext';
import { useWorkspace } from '@/contexts/WorkspaceContext';
import { BUSY_TITLE } from '@/lib/import-ui';
import { REPO_URL, openExternal } from '@/lib/electron';

type Pending =
  | { kind: 'rebuild' }
  | { kind: 'restore'; file: File }
  | { kind: 'clear' }
  | null;

function errorText(e: unknown, fallback: string): string {
  return e instanceof Error && e.message ? e.message : fallback;
}

function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  destructive = false,
  confirmDisabled = false,
  onConfirm,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: ReactNode;
  confirmLabel: string;
  destructive?: boolean;
  confirmDisabled?: boolean;
  onConfirm: () => void;
  children?: ReactNode;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (!confirmDisabled) onConfirm();
          }}
        >
          {children}
          <DialogFooter>
            <Button type="button" variant="outline" size="sm" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" size="sm" variant={destructive ? 'destructive' : 'default'} disabled={confirmDisabled}>
              {confirmLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

const triggerClass =
  'h-7 rounded-control px-2 font-normal text-muted-foreground hover:bg-overlay-hover hover:text-foreground focus:bg-overlay-selected focus:text-foreground data-[state=open]:bg-overlay-selected data-[state=open]:text-foreground';

/** File / Database / Help menus in the caption row. */
export default function AppMenuBar() {
  const navigate = useNavigate();
  const {
    phase,
    setShowImportOverlay,
    setShowDatabaseImport,
    canCancelImport,
    cancelImport,
    startSampleImport,
    startRebuild,
    exportDatabase,
    importDatabase,
    clearDb,
  } = useImport();
  const { activeWorkspace, totalHands } = useWorkspace();
  const fileRef = useRef<HTMLInputElement>(null);
  const [pending, setPending] = useState<Pending>(null);
  const [typed, setTyped] = useState('');

  const busy = phase === 'uploading' || phase === 'rebuilding';
  const workspaceName = activeWorkspace?.name ?? 'this workspace';
  const workspaceHands = activeWorkspace?.hand_count ?? 0;
  const close = () => {
    setPending(null);
    setTyped('');
  };

  const runSample = async () => {
    try {
      await startSampleImport();
    } catch (e) {
      toast.error(errorText(e, 'Could not load the sample hands'));
    }
  };

  const runBackup = async () => {
    try {
      await exportDatabase();
    } catch (e) {
      toast.error(errorText(e, 'Backup failed'));
    }
  };

  const runRestore = async (file: File) => {
    close();
    try {
      await importDatabase(file);
      toast.success(`Database restored from "${file.name}"`);
    } catch (e) {
      toast.error(errorText(e, 'Restore failed'));
    }
  };

  const runClear = async () => {
    close();
    try {
      await clearDb();
      toast.success(`Cleared all hands from "${workspaceName}"`);
    } catch (e) {
      toast.error(errorText(e, 'Clearing hands failed'));
    }
  };

  return (
    <>
      <Menubar className="h-auto gap-0.5 border-0 bg-transparent p-0 shadow-none">
        <MenubarMenu>
          <MenubarTrigger className={triggerClass}>File</MenubarTrigger>
          <MenubarContent>
            <MenubarItem disabled={phase !== 'idle'} title={phase !== 'idle' ? BUSY_TITLE : undefined} onSelect={() => setShowImportOverlay(true)}>
              <FolderUp />
              Import Hand Histories…
            </MenubarItem>
            <MenubarItem disabled={phase !== 'idle'} title={phase !== 'idle' ? BUSY_TITLE : undefined} onSelect={() => setShowDatabaseImport(true)}>
              <FolderInput />
              Import From Database…
            </MenubarItem>
            <MenubarSeparator />
            <MenubarItem disabled={phase !== 'idle'} title={phase !== 'idle' ? BUSY_TITLE : undefined} onSelect={runSample}>
              <Sparkles />
              Use Sample Data
            </MenubarItem>
          </MenubarContent>
        </MenubarMenu>

        <MenubarMenu>
          <MenubarTrigger className={triggerClass}>Database</MenubarTrigger>
          <MenubarContent>
            {phase === 'uploading' && (
              <>
                <MenubarItem disabled={!canCancelImport} onSelect={cancelImport}>
                  <XCircle />
                  Cancel Import
                </MenubarItem>
                <MenubarSeparator />
              </>
            )}
            <MenubarItem
              disabled={phase !== 'idle' || totalHands === 0}
              onSelect={() => setPending({ kind: 'rebuild' })}
            >
              <RefreshCw />
              Rebuild Statistics…
            </MenubarItem>
            <MenubarSeparator />
            <MenubarItem disabled={busy || totalHands === 0} onSelect={runBackup}>
              <DatabaseBackup />
              Back Up Database…
            </MenubarItem>
            <MenubarItem disabled={busy} onSelect={() => fileRef.current?.click()}>
              <FileInput />
              Restore Database…
            </MenubarItem>
            <MenubarItem
              variant="destructive"
              disabled={busy || workspaceHands === 0}
              onSelect={() => setPending({ kind: 'clear' })}
            >
              <Trash2 />
              Clear Workspace Hands…
            </MenubarItem>
            <MenubarSeparator />
            <MenubarItem onSelect={() => navigate('/databases')}>
              <Layers />
              Workspaces…
            </MenubarItem>
          </MenubarContent>
        </MenubarMenu>

        <MenubarMenu>
          <MenubarTrigger className={triggerClass}>Help</MenubarTrigger>
          <MenubarContent>
            <MenubarItem onSelect={() => navigate('/configuration/updates')}>
              <RotateCw />
              Check for Updates
            </MenubarItem>
            <MenubarSeparator />
            <MenubarItem onSelect={() => navigate('/configuration/about')}>
              <Info />
              About Open Holdem Manager
            </MenubarItem>
            <MenubarItem onSelect={() => openExternal(REPO_URL)}>
              <ExternalLink />
              GitHub
            </MenubarItem>
          </MenubarContent>
        </MenubarMenu>
      </Menubar>

      <input
        ref={fileRef}
        type="file"
        accept=".duckdb"
        className="hidden"
        tabIndex={-1}
        aria-hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = '';
          if (file) setPending({ kind: 'restore', file });
        }}
      />

      <ConfirmDialog
        open={pending?.kind === 'rebuild'}
        onOpenChange={(o) => !o && close()}
        title="Rebuild statistics?"
        description={`Recomputes every stat for all ${totalHands.toLocaleString()} stored hands with the current parser. The app stays usable while it runs; progress shows in the status bar.`}
        confirmLabel="Rebuild"
        onConfirm={() => {
          close();
          startRebuild();
        }}
      />

      <ConfirmDialog
        open={pending?.kind === 'restore'}
        onOpenChange={(o) => !o && close()}
        title="Restore database?"
        description={
          pending?.kind === 'restore' ? (
            <>
              This replaces <span className="text-foreground">all data in every workspace</span> with the
              contents of "{pending.file.name}". The current database is kept as poker.duckdb.bak.
            </>
          ) : null
        }
        confirmLabel="Replace all data"
        destructive
        onConfirm={() => pending?.kind === 'restore' && runRestore(pending.file)}
      />

      <ConfirmDialog
        open={pending?.kind === 'clear'}
        onOpenChange={(o) => !o && close()}
        title={`Clear hands from "${workspaceName}"?`}
        description={`Deletes all ${workspaceHands.toLocaleString()} hands, tags and notes in this workspace. Other workspaces are not touched. This cannot be undone.`}
        confirmLabel="Clear hands"
        destructive
        confirmDisabled={typed.trim() !== workspaceName}
        onConfirm={runClear}
      >
        <label className="flex flex-col gap-1.5 text-sm text-muted-foreground">
          <span>
            Type <span className="font-medium text-foreground">{workspaceName}</span> to confirm
          </span>
          <Input value={typed} onChange={(e) => setTyped(e.target.value)} autoFocus autoComplete="off" />
        </label>
      </ConfirmDialog>
    </>
  );
}
