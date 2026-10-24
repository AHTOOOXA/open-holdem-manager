import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { FolderOpen, Pencil, Plus, TriangleAlert, X } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { useWorkspace } from '@/contexts/WorkspaceContext';
import { getElectronAPI } from '@/lib/electron';
import { AUTO_IMPORT_DEFAULTS, AUTO_IMPORT_STATUS_KEY, addFolder, getAutoImportStatus, isAbsolutePath, megabytes, removeFolder, replaceFolder } from '@/lib/import/auto-import';
import type { AutoImportConfig } from '@/lib/import/types';
import { grouped } from '@/lib/format';
import { ConfigError, ConfigLoading } from './ConfigState';
import OptionRow from './OptionRow';
import SectionHeader from './SectionHeader';
import { useConfigSection } from './useConfigSection';

const DEFAULT_ARCHIVE_TEXT = 'Documents/OHM Hand Archive in your home folder';

/** A path the user types (browser) or picks (Electron). */
function PathAdder({ placeholder, buttonLabel, onAdd }: { placeholder: string; buttonLabel: string; onAdd: (path: string) => void }) {
  const [text, setText] = useState('');
  const trimmed = text.trim();
  const bad = trimmed !== '' && !isAbsolutePath(trimmed);
  return (
    <form
      className="flex flex-col gap-1"
      onSubmit={(e) => {
        e.preventDefault();
        if (trimmed && !bad) {
          onAdd(trimmed);
          setText('');
        }
      }}
    >
      <div className="flex gap-2">
        <Input value={text} onChange={(e) => setText(e.target.value)} placeholder={placeholder} aria-label={placeholder} aria-invalid={bad} />
        <Button type="submit" variant="outline" disabled={!trimmed || bad}>
          <Plus aria-hidden />
          {buttonLabel}
        </Button>
      </div>
      {bad && <p role="alert" className="text-xs text-money-neg">Use a full path, for example /Users/you/HandHistory or C:\HandHistory.</p>}
    </form>
  );
}

export default function AutoImportSection() {
  const { env, isError, error, update, reset } = useConfigSection<AutoImportConfig>('auto_import');
  const { workspaces, activeWorkspaceId } = useWorkspace();
  const pick = getElectronAPI()?.pickFolder;
  const cfg = env?.value;
  const statusQuery = useQuery({
    queryKey: AUTO_IMPORT_STATUS_KEY,
    queryFn: getAutoImportStatus,
    enabled: cfg?.enabled === true,
    refetchInterval: 5000,
  });

  if (isError) return <ConfigError error={error} />;
  if (!cfg) return <ConfigLoading />;
  const d = AUTO_IMPORT_DEFAULTS;
  const target = cfg.workspace_id ?? workspaces[0]?.id ?? activeWorkspaceId;
  const large = statusQuery.data?.large_folders ?? [];

  const addPicked = async () => {
    const path = await pick?.();
    if (path) update((c) => ({ ...c, folders: addFolder(c.folders, path).folders }));
  };
  const rePick = async (index: number) => {
    const path = await pick?.(cfg.folders[index]);
    if (path) update((c) => ({ ...c, folders: replaceFolder(c.folders, index, path) }));
  };
  const pickArchive = async () => {
    const path = await pick?.(cfg.archive_dir ?? undefined);
    if (path) update((c) => ({ ...c, archive_dir: path }));
  };

  return (
    <div>
      <SectionHeader
        title="Auto Import"
        caption="Watches folders and imports new hands while you play. Needs the folders to hold hand history files (.txt, .xml)."
        onReset={() => reset()}
        resetDescription="Auto import is turned off and the folder list and archive settings are cleared."
      />
      <OptionRow id="auto-import-enabled" label="Auto import" changed={cfg.enabled !== d.enabled}>
        <Switch
          id="auto-import-enabled"
          checked={cfg.enabled}
          onCheckedChange={(v) => update((c) => ({ ...c, enabled: v, workspace_id: v && c.workspace_id == null ? activeWorkspaceId : c.workspace_id }))}
        />
      </OptionRow>
      <OptionRow id="auto-import-workspace" label="Import into" help="New hands go to this workspace, whichever one you are looking at.">
        <Select value={String(target)} onValueChange={(v) => update((c) => ({ ...c, workspace_id: Number(v) }))}>
          <SelectTrigger id="auto-import-workspace" className="w-56">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {workspaces.map((w) => (
              <SelectItem key={w.id} value={String(w.id)}>{w.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </OptionRow>

      {large.length > 0 && (
        <Alert className="my-3">
          <TriangleAlert aria-hidden />
          <AlertTitle>Some folders are large</AlertTitle>
          <AlertDescription>
            {large.map((f) => (
              <span key={f.path} className="block truncate">{f.path} ({grouped(megabytes(f.bytes))} MB)</span>
            ))}
            <span className="block">Auto import keeps working, but cleaning or archiving old files keeps it fast.</span>
          </AlertDescription>
        </Alert>
      )}

      <div className="border-b border-border-subtle py-3">
        <h3 className="mb-2 text-sm font-medium">Auto Import Folders</h3>
        {cfg.folders.length === 0 ? (
          <p className="mb-2 text-sm text-muted-foreground">No folders yet. Add the folder your poker client writes hand histories to.</p>
        ) : (
          <ul className="mb-2 divide-y divide-border-subtle rounded-card border border-border">
            {cfg.folders.map((f, i) => (
              <li key={f} className="flex items-center gap-2 px-3 py-1.5 text-sm">
                <FolderOpen className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                <span className="min-w-0 flex-1 truncate" title={f}>{f}</span>
                {pick && (
                  <Button variant="ghost" size="icon-xs" aria-label={`Change folder ${f}`} onClick={() => void rePick(i)}>
                    <Pencil />
                  </Button>
                )}
                <Button variant="ghost" size="icon-xs" aria-label={`Remove folder ${f}`} onClick={() => update((c) => ({ ...c, folders: removeFolder(c.folders, i) }))}>
                  <X />
                </Button>
              </li>
            ))}
          </ul>
        )}
        {pick ? (
          <Button variant="outline" onClick={() => void addPicked()}>
            <Plus aria-hidden />
            Add folder…
          </Button>
        ) : (
          <PathAdder placeholder="Absolute folder path" buttonLabel="Add folder" onAdd={(p) => update((c) => ({ ...c, folders: addFolder(c.folders, p).folders }))} />
        )}
      </div>

      <OptionRow
        id="auto-import-archive"
        label="Archive hand histories"
        help="Moves files of earlier days (today's files stay put), once untouched for 5 minutes and all their hands are stored, into the archive folder, sorted by site and date. Your original files are moved, not copied. The archive folder must not be (or contain) a watched folder."
        changed={cfg.archive_enabled !== d.archive_enabled}
      >
        <Switch id="auto-import-archive" checked={cfg.archive_enabled} onCheckedChange={(v) => update((c) => ({ ...c, archive_enabled: v }))} />
      </OptionRow>
      <p className="-mt-1 pb-2 text-xs text-muted-foreground">Off by default: turning it on moves your hand history files out of the watched folders.</p>
      {cfg.archive_enabled && (
        <div className="flex items-center gap-2 py-2 text-sm">
          <span className="text-muted-foreground">Archive folder</span>
          {pick ? (
            <>
              <span className="min-w-0 flex-1 truncate" title={cfg.archive_dir ?? DEFAULT_ARCHIVE_TEXT}>{cfg.archive_dir ?? DEFAULT_ARCHIVE_TEXT}</span>
              <Button variant="outline" size="sm" onClick={() => void pickArchive()}>Change folder…</Button>
            </>
          ) : (
            <div className="min-w-0 flex-1">
              <PathAdder placeholder={cfg.archive_dir ?? DEFAULT_ARCHIVE_TEXT} buttonLabel="Set" onAdd={(p) => update((c) => ({ ...c, archive_dir: p }))} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
