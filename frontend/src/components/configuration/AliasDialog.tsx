import { useState } from 'react';
import { Plus, X } from 'lucide-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { addAlias, createIdentity, getPlayers, removeAlias, updateIdentity, type Identity } from '@/lib/api';
import { diffMembers, type Member } from '@/lib/config/logic';
import { useWorkspace } from '@/contexts/WorkspaceContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { count } from '@/lib/format';

function membersOf(identity: Identity | null): Member[] {
  return (identity?.aliases ?? []).map((a) => ({ playerId: a.player_id, workspaceId: a.workspace_id, username: a.username, aliasId: a.id }));
}

/** Create or edit an alias: name, single-person flag, members (left) and workspace players to add (right). */
export default function AliasDialog({ identity, onClose }: { identity: Identity | null; onClose: () => void }) {
  const qc = useQueryClient();
  const { activeWorkspaceId } = useWorkspace();
  const [name, setName] = useState(identity?.display_name ?? '');
  const [single, setSingle] = useState(identity?.is_single_person ?? false);
  const [members, setMembers] = useState<Member[]>(() => membersOf(identity));
  const [search, setSearch] = useState('');
  const [saving, setSaving] = useState(false);

  const { data } = useQuery({
    queryKey: ['alias-player-search', search, activeWorkspaceId],
    queryFn: ({ signal }) => getPlayers({ search: search || undefined, min_hands: 1, per_page: 30 }, signal),
  });
  const taken = new Set(members.map((m) => `${m.workspaceId}:${m.playerId}`));
  const candidates = (data?.players ?? []).filter((p) => !taken.has(`${activeWorkspaceId}:${p.id}`));

  const save = async () => {
    const trimmed = name.trim();
    if (!trimmed || saving) return;
    setSaving(true);
    try {
      const target = identity
        ? await updateIdentity(identity.id, { display_name: trimmed, is_single_person: single })
        : await createIdentity({ display_name: trimmed });
      if (!identity && single) await updateIdentity(target.id, { is_single_person: true });
      const { add, remove } = diffMembers(membersOf(identity), members);
      for (const m of remove) if (m.aliasId !== undefined) await removeAlias(target.id, m.aliasId);
      for (const m of add) await addAlias(target.id, { workspace_id: m.workspaceId, player_id: m.playerId });
      await qc.invalidateQueries({ queryKey: ['identities'] });
      onClose();
    } catch (e) {
      toast.error('Saving the alias failed', { description: e instanceof Error ? e.message : undefined });
      await qc.invalidateQueries({ queryKey: ['identities'] });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{identity ? 'Edit alias' : 'Add alias'}</DialogTitle>
          <DialogDescription>An alias joins the nicknames of one person (or one shared account) into a single player.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="flex items-end gap-4">
            <div className="flex flex-1 flex-col gap-1.5">
              <label htmlFor="alias-name" className="text-sm font-medium">Name</label>
              <Input id="alias-name" value={name} autoFocus onChange={(e) => setName(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') void save(); }} />
            </div>
            <label className="flex h-control items-center gap-2 text-sm">
              <Switch checked={single} onCheckedChange={setSingle} />
              Is single person
            </label>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <section aria-label="Members" className="flex min-h-56 flex-col rounded-card border border-border">
              <h3 className="border-b border-border px-3 py-2 text-sm font-medium">Members ({members.length})</h3>
              <ul className="max-h-56 flex-1 overflow-y-auto">
                {members.map((m) => (
                  <li key={`${m.workspaceId}:${m.playerId}`} className="group flex h-row items-center justify-between px-3 hover:bg-overlay-hover">
                    <span className="truncate text-sm">{m.username}</span>
                    <Button variant="ghost" size="icon" className="size-6" aria-label={`Remove ${m.username}`} onClick={() => setMembers(members.filter((x) => x !== m))}>
                      <X className="size-3.5" />
                    </Button>
                  </li>
                ))}
                {members.length === 0 && <li className="px-3 py-3 text-sm text-muted-foreground">No players yet. Add some from the right.</li>}
              </ul>
            </section>
            <section aria-label="Workspace players" className="flex min-h-56 flex-col rounded-card border border-border">
              <div className="border-b border-border p-2">
                <Input aria-label="Search workspace players" placeholder="Search players…" value={search} onChange={(e) => setSearch(e.target.value)} className="h-control" />
              </div>
              <ul className="max-h-56 flex-1 overflow-y-auto">
                {candidates.map((p) => (
                  <li key={p.id}>
                    <button
                      type="button"
                      className="flex h-row w-full items-center justify-between gap-2 px-3 text-left text-sm outline-none hover:bg-overlay-hover focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-inset"
                      aria-label={`Add ${p.username}`}
                      onClick={() => setMembers([...members, { playerId: p.id, workspaceId: activeWorkspaceId, username: p.username }])}
                    >
                      <span className="truncate">{p.username}</span>
                      <span className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">{count(p.hands)} hands<Plus className="size-3.5" aria-hidden /></span>
                    </button>
                  </li>
                ))}
                {candidates.length === 0 && <li className="px-3 py-3 text-sm text-muted-foreground">{search ? 'No players found' : 'No players to add'}</li>}
              </ul>
            </section>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={saving}>Cancel</Button>
          <Button onClick={() => void save()} disabled={!name.trim() || saving}>{saving ? 'Saving…' : 'Save'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
