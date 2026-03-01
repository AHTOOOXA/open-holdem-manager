import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getIdentity, getIdentityStats, updateIdentity, deleteIdentity,
  removeAlias, addAlias, getPlayers,
} from '@/lib/api';
import type { Identity } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { ArrowLeft, Plus, Trash2, X } from 'lucide-react';
import { useWorkspace } from '@/contexts/WorkspaceContext';

const WELL_KNOWN_TAGS = ['me', 'student', 'reg', 'fish', 'coach'] as const;
const TAG_COLORS: Record<string, string> = {
  me: 'bg-primary/20 text-primary border-primary/30',
  student: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  reg: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  fish: 'bg-green/20 text-green border-green/30',
  coach: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
};

function StatRow({ label, value, sample }: { label: string; value: number | null; sample: number }) {
  return (
    <div className="flex items-center justify-between py-1 text-[13px]">
      <span className="text-text-muted">{label}</span>
      <div className="flex items-center gap-2">
        <span className="font-mono">{value !== null ? value.toFixed(1) : '\u2014'}</span>
        <span className="text-[11px] text-text-muted">({sample})</span>
      </div>
    </div>
  );
}

function AddAliasDialog({
  open,
  onOpenChange,
  identityId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  identityId: number;
}) {
  const qc = useQueryClient();
  const { activeWorkspaceId } = useWorkspace();
  const [search, setSearch] = useState('');

  const { data } = useQuery({
    queryKey: ['alias-search', search, activeWorkspaceId],
    queryFn: () => getPlayers({ search: search || undefined, min_hands: 1, per_page: 20 }),
    enabled: open,
  });

  const linkMut = useMutation({
    mutationFn: (playerId: number) => addAlias(identityId, { workspace_id: activeWorkspaceId, player_id: playerId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.identities.detail(identityId) });
      qc.invalidateQueries({ queryKey: queryKeys.identities.list });
      onOpenChange(false);
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Link Player Alias</DialogTitle>
        </DialogHeader>
        <Input
          placeholder="Search players..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="h-8 text-[13px]"
          autoFocus
        />
        {data && data.players.length > 0 ? (
          <div className="space-y-1 max-h-60 overflow-y-auto">
            {data.players.map((p) => (
              <button
                key={p.id}
                onClick={() => linkMut.mutate(p.id)}
                disabled={linkMut.isPending}
                className="w-full text-left p-2 rounded hover:bg-surface-hover transition-colors flex items-center justify-between text-[13px]"
              >
                <span>{p.username}</span>
                <span className="text-text-muted">{p.hands} hands</span>
              </button>
            ))}
          </div>
        ) : (
          <p className="text-[13px] text-text-muted text-center py-4">
            {search ? 'No players found' : 'Type to search'}
          </p>
        )}
        {linkMut.isError && (
          <p className="text-red text-[12px]">Failed to link. Player may already be linked.</p>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default function IdentityDetailPage() {
  const { identityId } = useParams<{ identityId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const id = Number(identityId);

  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState('');
  const [editNotes, setEditNotes] = useState('');
  const [editTags, setEditTags] = useState<string[]>([]);
  const [showAddAlias, setShowAddAlias] = useState(false);

  const { data: identity, isPending } = useQuery({
    queryKey: queryKeys.identities.detail(id),
    queryFn: () => getIdentity(id),
    enabled: !isNaN(id),
  });

  const { data: stats } = useQuery({
    queryKey: queryKeys.identities.stats(id, {}),
    queryFn: () => getIdentityStats(id),
    enabled: !isNaN(id),
  });

  const updateMut = useMutation({
    mutationFn: (data: Partial<{ display_name: string; notes: string; tags: string[] }>) =>
      updateIdentity(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.identities.detail(id) });
      qc.invalidateQueries({ queryKey: queryKeys.identities.list });
      setEditing(false);
    },
  });

  const deleteMut = useMutation({
    mutationFn: () => deleteIdentity(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.identities.list });
      navigate('/players');
    },
  });

  const unlinkMut = useMutation({
    mutationFn: (aliasId: number) => removeAlias(id, aliasId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.identities.detail(id) });
      qc.invalidateQueries({ queryKey: queryKeys.identities.list });
    },
  });

  const startEditing = (ident: Identity) => {
    setEditName(ident.display_name);
    setEditNotes(ident.notes || '');
    setEditTags([...ident.tags]);
    setEditing(true);
  };

  const toggleTag = (tag: string) => {
    setEditTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag],
    );
  };

  if (isPending) {
    return <p className="text-text-muted text-sm py-8 text-center">Loading...</p>;
  }

  if (!identity) {
    return <p className="text-red text-sm py-8 text-center">Identity not found</p>;
  }

  return (
    <div className="max-w-3xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button onClick={() => navigate('/players')} className="text-text-muted hover:text-text">
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex items-center gap-2 flex-1">
          {identity.color && (
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: identity.color }} />
          )}
          <h1 className="text-lg font-semibold">{identity.display_name}</h1>
          <span className="text-[13px] text-text-muted font-mono">
            {identity.total_hands.toLocaleString()} hands
          </span>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => startEditing(identity)}>
            Edit
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="text-red hover:text-red"
            onClick={() => { if (confirm('Delete this identity?')) deleteMut.mutate(); }}
          >
            <Trash2 className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>

      {/* Tags */}
      {identity.tags.length > 0 && (
        <div className="flex gap-1.5 flex-wrap">
          {identity.tags.map((tag) => (
            <Badge key={tag} variant="outline" className={`text-[12px] ${TAG_COLORS[tag] || ''}`}>
              {tag}
            </Badge>
          ))}
        </div>
      )}

      {/* Notes */}
      {identity.notes && (
        <p className="text-[13px] text-text-muted">{identity.notes}</p>
      )}

      {/* Edit Dialog */}
      <Dialog open={editing} onOpenChange={setEditing}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Edit Identity</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <label className="text-[12px] text-text-muted mb-1 block">Display Name</label>
              <Input value={editName} onChange={(e) => setEditName(e.target.value)} className="h-8 text-[13px]" />
            </div>
            <div>
              <label className="text-[12px] text-text-muted mb-1 block">Notes</label>
              <Textarea value={editNotes} onChange={(e) => setEditNotes(e.target.value)} className="text-[13px] min-h-[60px]" />
            </div>
            <div>
              <label className="text-[12px] text-text-muted mb-1 block">Tags</label>
              <div className="flex gap-1.5 flex-wrap">
                {WELL_KNOWN_TAGS.map((tag) => (
                  <button
                    key={tag}
                    onClick={() => toggleTag(tag)}
                    className={`text-[12px] px-2.5 py-1 rounded-full border transition-colors ${
                      editTags.includes(tag)
                        ? TAG_COLORS[tag] || 'bg-surface-hover border-border'
                        : 'border-border text-text-muted hover:text-text'
                    }`}
                  >
                    {tag}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" size="sm" onClick={() => setEditing(false)}>Cancel</Button>
              <Button
                size="sm"
                onClick={() => updateMut.mutate({
                  display_name: editName,
                  notes: editNotes,
                  tags: editTags,
                })}
                disabled={updateMut.isPending}
              >
                Save
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Aliases */}
      <section>
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-[14px] font-semibold">Linked Players</h2>
          <Button variant="outline" size="sm" onClick={() => setShowAddAlias(true)}>
            <Plus className="w-3.5 h-3.5 mr-1" />
            Link Alias
          </Button>
        </div>
        {identity.aliases.length > 0 ? (
          <div className="space-y-1">
            {identity.aliases.map((alias) => (
              <div key={alias.id} className="flex items-center justify-between p-2 rounded bg-surface border border-border">
                <div>
                  <span className="text-[14px] font-medium">{alias.username}</span>
                  <span className="text-[12px] text-text-muted ml-2">{alias.workspace_name}</span>
                </div>
                <button
                  onClick={() => unlinkMut.mutate(alias.id)}
                  className="p-1 rounded hover:bg-red/20 text-text-muted hover:text-red transition-colors"
                  title="Unlink"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-[13px] text-text-muted text-center py-4">No linked players</p>
        )}
      </section>

      {/* Aggregated Stats */}
      {stats && stats.hands > 0 && (
        <section>
          <h2 className="text-[14px] font-semibold mb-2">Aggregated Stats</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 border border-border rounded-lg p-3 bg-surface">
            <div>
              <h3 className="text-[12px] text-text-muted uppercase tracking-wide mb-1">Preflop</h3>
              <StatRow label="VPIP" value={stats.vpip.total.value} sample={stats.vpip.total.sample} />
              <StatRow label="PFR" value={stats.pfr.total.value} sample={stats.pfr.total.sample} />
              <StatRow label="3-Bet" value={stats.three_bet.total.value} sample={stats.three_bet.total.sample} />
              <StatRow label="4-Bet" value={stats.four_bet.total.value} sample={stats.four_bet.total.sample} />
              <StatRow label="Fold to 3-Bet" value={stats.fold_to_3bet.total.value} sample={stats.fold_to_3bet.total.sample} />
              <StatRow label="Steal" value={stats.steal.total.value} sample={stats.steal.total.sample} />
            </div>
            <div>
              <h3 className="text-[12px] text-text-muted uppercase tracking-wide mb-1">Postflop</h3>
              <StatRow label="C-Bet Flop" value={stats.cbet_flop.total.value} sample={stats.cbet_flop.total.sample} />
              <StatRow label="Fold to C-Bet" value={stats.fold_to_cbet_flop.total.value} sample={stats.fold_to_cbet_flop.total.sample} />
              <StatRow label="WTSD" value={stats.wtsd.value} sample={stats.wtsd.sample} />
              <StatRow label="WSD" value={stats.wsd.value} sample={stats.wsd.sample} />
              <StatRow label="WWSF" value={stats.wwsf.value} sample={stats.wwsf.sample} />
              <StatRow label="AFq Flop" value={stats.afq_flop.value} sample={stats.afq_flop.sample} />
            </div>
          </div>
        </section>
      )}

      <AddAliasDialog
        open={showAddAlias}
        onOpenChange={setShowAddAlias}
        identityId={id}
      />
    </div>
  );
}
