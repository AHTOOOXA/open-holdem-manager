import { useRef, useState } from 'react';
import { Download, Pencil, Pin, PinOff, Plus, Trash2, Upload } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  IDENTITIES_EXPORT_URL, deleteIdentity, getIdentities, importIdentitiesCsv, updateIdentity, type Identity,
} from '@/lib/api';
import { filterAliases, sortAliases } from '@/lib/config/logic';
import { queryKeys } from '@/lib/query-keys';
import { useWorkspace } from '@/contexts/WorkspaceContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import ConfirmDialog from '@/components/databases/ConfirmDialog';
import { count } from '@/lib/format';
import { cn } from '@/lib/utils';
import AliasDialog from './AliasDialog';
import SectionHeader from './SectionHeader';
import { ConfigError, ConfigLoading } from './ConfigState';

function AliasCard({ identity, onEdit, onDelete, onPatch }: {
  identity: Identity;
  onEdit: () => void;
  onDelete: () => void;
  onPatch: (patch: { pinned?: boolean; is_single_person?: boolean }) => void;
}) {
  const n = identity.player_count ?? identity.aliases.length;
  return (
    <li className="group flex flex-col gap-2 rounded-card border border-border bg-surface-sunken p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            {identity.pinned && <Pin className="size-3 shrink-0 text-primary" aria-label="Pinned" />}
            <span className="truncate text-sm font-medium">{identity.display_name}</span>
          </div>
          <div className="text-xs text-muted-foreground">
            {n} {n === 1 ? 'player' : 'players'} · {count(identity.total_hands)} hands
          </div>
        </div>
        <div className="flex shrink-0 items-center opacity-0 group-focus-within:opacity-100 group-hover:opacity-100">
          <Button variant="ghost" size="icon" className="size-7" aria-label={`Edit ${identity.display_name}`} onClick={onEdit}><Pencil className="size-3.5" /></Button>
          <Button variant="ghost" size="icon" className="size-7" aria-label={`Delete ${identity.display_name}`} onClick={onDelete}><Trash2 className="size-3.5" /></Button>
        </div>
      </div>
      <div className="flex items-center justify-between gap-2">
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          <Switch checked={identity.is_single_person} aria-label={`${identity.display_name} is a single person`} onCheckedChange={(v) => onPatch({ is_single_person: v })} />
          Is single person
        </label>
        <Button
          variant="ghost"
          size="icon"
          className={cn('size-7', !identity.pinned && 'text-subtle-foreground')}
          aria-pressed={identity.pinned}
          aria-label={identity.pinned ? `Unpin ${identity.display_name}` : `Pin ${identity.display_name}`}
          onClick={() => onPatch({ pinned: !identity.pinned })}
        >
          {identity.pinned ? <PinOff className="size-3.5" /> : <Pin className="size-3.5" />}
        </Button>
      </div>
    </li>
  );
}

export default function AliasesSection() {
  const qc = useQueryClient();
  const { activeWorkspaceId } = useWorkspace();
  const { data, isError, error } = useQuery({ queryKey: queryKeys.identities.list, queryFn: getIdentities });
  const [search, setSearch] = useState('');
  const [dialog, setDialog] = useState<{ identity: Identity | null } | null>(null);
  const [deleting, setDeleting] = useState<Identity | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = () => qc.invalidateQueries({ queryKey: ['identities'] });
  const patch = useMutation({
    mutationFn: ({ id, p }: { id: number; p: { pinned?: boolean; is_single_person?: boolean } }) => updateIdentity(id, p),
    onSuccess: refresh,
    onError: (e: Error) => toast.error('Saving failed', { description: e.message }),
  });
  const remove = useMutation({
    mutationFn: (id: number) => deleteIdentity(id),
    onSuccess: refresh,
    onError: (e: Error) => toast.error('Delete failed', { description: e.message }),
  });
  const importCsv = useMutation({
    mutationFn: (file: File) => importIdentitiesCsv(activeWorkspaceId, file),
    onSuccess: (r) => {
      toast.success(`Imported ${r.aliases} aliases with ${r.players} players`, {
        description: r.skipped_lines > 0 ? `${r.skipped_lines} lines skipped (unknown site or nickname in this workspace).` : undefined,
      });
      void refresh();
    },
    onError: (e: Error) => toast.error('Import failed', { description: e.message }),
  });

  if (isError) return <ConfigError error={error} />;
  if (!data) return <ConfigLoading />;
  const shown = sortAliases(filterAliases(data, search));

  return (
    <div>
      <SectionHeader title="Aliases" caption="Group the nicknames of one person, or one shared account, under a single name." />
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Input aria-label="Search aliases" placeholder="Search by alias or nickname…" value={search} onChange={(e) => setSearch(e.target.value)} className="h-control w-64" />
        <div className="ml-auto flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()} disabled={importCsv.isPending}>
            <Upload className="size-3.5" />
            Import From CSV…
          </Button>
          {data.length > 0 && (
            <Button variant="outline" size="sm" asChild>
              <a href={IDENTITIES_EXPORT_URL} download="aliases.csv">
                <Download className="size-3.5" />
                Export to CSV…
              </a>
            </Button>
          )}
          <Button size="sm" onClick={() => setDialog({ identity: null })}>
            <Plus className="size-3.5" />
            Add Alias
          </Button>
        </div>
        <input
          ref={fileRef}
          type="file"
          accept=".csv,text/csv"
          className="sr-only"
          aria-label="CSV file with aliases"
          tabIndex={-1}
          onChange={(e) => {
            const f = e.target.files?.[0];
            e.target.value = '';
            if (f) importCsv.mutate(f);
          }}
        />
      </div>
      {shown.length === 0 ? (
        <p className="text-sm text-muted-foreground">{data.length === 0 ? 'No aliases yet.' : 'No alias matches the search.'}</p>
      ) : (
        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {shown.map((i) => (
            <AliasCard
              key={i.id}
              identity={i}
              onEdit={() => setDialog({ identity: i })}
              onDelete={() => setDeleting(i)}
              onPatch={(p) => patch.mutate({ id: i.id, p })}
            />
          ))}
        </ul>
      )}
      {dialog && <AliasDialog key={dialog.identity?.id ?? 'new'} identity={dialog.identity} onClose={() => setDialog(null)} />}
      <ConfirmDialog
        open={deleting !== null}
        title={`Delete the alias "${deleting?.display_name ?? ''}"?`}
        description="The players stay; they are no longer grouped."
        confirmLabel="Delete"
        destructive
        onConfirm={() => {
          if (deleting) remove.mutate(deleting.id);
          setDeleting(null);
        }}
        onCancel={() => setDeleting(null)}
      />
    </div>
  );
}
