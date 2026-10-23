import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Bookmark, Pencil, Plus, Trash2 } from 'lucide-react';
import { createCheckpoint, updateCheckpoint, deleteCheckpoint, getCheckpoints } from '@/lib/api';
import type { Workspace, Checkpoint } from '@/contexts/WorkspaceContext';
import { useWorkspace } from '@/contexts/WorkspaceContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { DatePicker } from '@/components/ui/date-picker';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { formatLocalDate, formatHHMM, formatCheckpointDateTime } from '@/lib/format';

interface Draft {
  /** null = new checkpoint */
  id: number | null;
  name: string;
  date: string;
  time: string;
  note: string;
}

function newDraft(): Draft {
  const now = new Date();
  return { id: null, name: '', date: formatLocalDate(now), time: formatHHMM(now), note: '' };
}

function draftOf(cp: Checkpoint): Draft {
  return {
    id: cp.id,
    name: cp.name,
    date: cp.checkpoint_at.slice(0, 10),
    time: formatHHMM(new Date(cp.checkpoint_at)),
    note: cp.note ?? '',
  };
}

interface Props {
  workspace: Workspace;
  onClose: () => void;
}

/** Lists a workspace's checkpoints with add / edit / delete. Mount only while open. */
export default function CheckpointsDialog({ workspace, onClose }: Props) {
  const qc = useQueryClient();
  const { refetchCheckpoints } = useWorkspace();
  const { data: checkpoints = [] } = useQuery({
    queryKey: ['checkpoints', workspace.id],
    queryFn: () => getCheckpoints(workspace.id),
  });
  const [draft, setDraft] = useState<Draft | null>(null);
  const [saving, setSaving] = useState(false);

  const refresh = async () => {
    await qc.invalidateQueries({ queryKey: ['checkpoints', workspace.id] });
    await refetchCheckpoints();
  };

  const save = async () => {
    if (!draft || !draft.name.trim()) return;
    setSaving(true);
    try {
      const body = {
        name: draft.name.trim(),
        checkpoint_at: `${draft.date}T${draft.time || '00:00'}:00`,
        note: draft.note.trim() || undefined,
      };
      if (draft.id === null) await createCheckpoint(workspace.id, body);
      else await updateCheckpoint(workspace.id, draft.id, body);
      await refresh();
      setDraft(null);
    } finally {
      setSaving(false);
    }
  };

  const remove = async (cp: Checkpoint) => {
    await deleteCheckpoint(workspace.id, cp.id);
    await refresh();
  };

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Checkpoints</DialogTitle>
          <DialogDescription>Mark a moment in {workspace.name} to compare before and after.</DialogDescription>
        </DialogHeader>

        {draft ? (
          <div className="flex flex-col gap-3 py-2">
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">Name</label>
              <Input
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                placeholder="e.g., Strategy change"
                autoFocus
                onKeyDown={(e) => { if (e.key === 'Enter') void save(); }}
              />
            </div>
            <div className="flex gap-3">
              <div className="flex flex-col gap-1.5 flex-1">
                <label className="text-sm font-medium">Date</label>
                <DatePicker
                  value={draft.date}
                  onChange={(v) => setDraft({ ...draft, date: v || draft.date })}
                  placeholder="Checkpoint date"
                  className="h-9 text-sm w-full"
                />
              </div>
              <div className="flex flex-col gap-1.5 w-24">
                <label className="text-sm font-medium">Time</label>
                <Input
                  type="time"
                  value={draft.time}
                  onChange={(e) => setDraft({ ...draft, time: e.target.value })}
                  className="h-9 text-sm"
                />
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">
                Note <span className="text-muted-foreground font-normal">(optional)</span>
              </label>
              <Input value={draft.note} onChange={(e) => setDraft({ ...draft, note: e.target.value })} placeholder="What changed?" />
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDraft(null)} disabled={saving}>Back</Button>
              <Button onClick={save} disabled={!draft.name.trim() || saving}>
                {saving ? 'Saving...' : draft.id === null ? 'Create' : 'Save'}
              </Button>
            </DialogFooter>
          </div>
        ) : (
          <>
            <div className="flex flex-col">
              {checkpoints.length === 0 && (
                <p className="py-3 text-sm text-muted-foreground">No checkpoints yet.</p>
              )}
              {checkpoints.map((cp) => (
                <div key={cp.id} className="group flex h-row items-center justify-between gap-2 rounded-control px-2 text-sm hover:bg-overlay-hover">
                  <div className="flex min-w-0 items-center gap-2">
                    <Bookmark className="size-3.5 shrink-0 text-subtle-foreground" />
                    <span className="truncate font-medium">{cp.name}</span>
                    <span className="shrink-0 text-xs text-muted-foreground">{formatCheckpointDateTime(cp.checkpoint_at)}</span>
                    {cp.note && <span className="truncate text-xs text-muted-foreground">{cp.note}</span>}
                  </div>
                  <div className="flex shrink-0 items-center gap-1 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100">
                    <Button size="icon" variant="ghost" className="size-6" aria-label={`Edit ${cp.name}`} onClick={() => setDraft(draftOf(cp))}>
                      <Pencil className="size-3" />
                    </Button>
                    <Button size="icon" variant="ghost" className="size-6 text-destructive hover:text-destructive" aria-label={`Delete ${cp.name}`} onClick={() => remove(cp)}>
                      <Trash2 className="size-3" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={onClose}>Close</Button>
              <Button onClick={() => setDraft(newDraft())}>
                <Plus className="size-3.5" />
                Add checkpoint
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
