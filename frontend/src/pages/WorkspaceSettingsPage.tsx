import { useState, useCallback } from 'react';
import { Pencil, Trash2, Bookmark, Plus } from 'lucide-react';
import { useWorkspace } from '@/contexts/WorkspaceContext';
import type { Workspace, Checkpoint } from '@/contexts/WorkspaceContext';
import {
  createWorkspace,
  updateWorkspace,
  deleteWorkspace,
  createCheckpoint,
  updateCheckpoint,
  deleteCheckpoint,
} from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { DatePicker } from '@/components/ui/date-picker';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from '@/components/ui/dropdown-menu';

const PRESET_COLORS = [
  { label: 'Gray', value: null },
  { label: 'Blue', value: '#3b82f6' },
  { label: 'Green', value: '#22c55e' },
  { label: 'Purple', value: '#a855f7' },
  { label: 'Orange', value: '#f97316' },
  { label: 'Pink', value: '#ec4899' },
  { label: 'Red', value: '#ef4444' },
  { label: 'Yellow', value: '#eab308' },
  { label: 'Cyan', value: '#06b6d4' },
];

function ColorDot({ color, className }: { color: string | null; className?: string }) {
  return (
    <span
      className={`inline-block size-3 shrink-0 rounded-full ${className ?? ''}`}
      style={{ backgroundColor: color ?? '#6b7280' }}
    />
  );
}

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatCheckpointDateTime(iso: string): string {
  const d = new Date(iso);
  const date = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  const time = `${hh}:${mm}`;
  return time !== '00:00' ? `${date} ${time}` : date;
}

export default function WorkspaceSettingsPage() {
  const {
    workspaces,
    activeWorkspaceId,
    setActiveWorkspaceId,
    checkpoints,
    refetchWorkspaces,
    refetchCheckpoints,
  } = useWorkspace();

  // Edit/Create workspace dialog
  const [editWs, setEditWs] = useState<Workspace | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [editName, setEditName] = useState('');
  const [editHero, setEditHero] = useState('');
  const [editDesc, setEditDesc] = useState('');
  const [editColor, setEditColor] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Delete workspace dialog
  const [deleteWs, setDeleteWs] = useState<Workspace | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState('');
  const [deleting, setDeleting] = useState(false);

  // Checkpoint dialog
  const [cpDialogWs, setCpDialogWs] = useState<Workspace | null>(null);
  const [newCpName, setNewCpName] = useState('');
  const [newCpDate, setNewCpDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [newCpTime, setNewCpTime] = useState(() => {
    const now = new Date();
    return `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
  });
  const [newCpNote, setNewCpNote] = useState('');
  const [creatingCp, setCreatingCp] = useState(false);

  // Edit checkpoint dialog
  const [editCp, setEditCp] = useState<Checkpoint | null>(null);
  const [editCpWsId, setEditCpWsId] = useState<number>(0);
  const [editCpName, setEditCpName] = useState('');
  const [editCpDate, setEditCpDate] = useState('');
  const [editCpTime, setEditCpTime] = useState('00:00');
  const [editCpNote, setEditCpNote] = useState('');
  const [savingCp, setSavingCp] = useState(false);

  const openEdit = useCallback((ws: Workspace) => {
    setIsCreating(false);
    setEditWs(ws);
    setEditName(ws.name);
    setEditHero(ws.hero_username);
    setEditDesc(ws.description ?? '');
    setEditColor(ws.color);
  }, []);

  const openCreate = useCallback(() => {
    setEditWs(null);
    setIsCreating(true);
    setEditName('');
    setEditHero('Hero');
    setEditDesc('');
    setEditColor(null);
  }, []);

  const closeWsDialog = useCallback(() => {
    setEditWs(null);
    setIsCreating(false);
  }, []);

  const handleSave = async () => {
    if (!editName.trim()) return;
    setSaving(true);
    try {
      if (isCreating) {
        await createWorkspace({
          name: editName.trim(),
          hero_username: editHero.trim() || 'Hero',
          description: editDesc.trim() || undefined,
          color: editColor ?? undefined,
        });
      } else if (editWs) {
        await updateWorkspace(editWs.id, {
          name: editName.trim(),
          hero_username: editHero.trim() || 'Hero',
          description: editDesc.trim() || undefined,
          color: editColor ?? undefined,
        });
      }
      await refetchWorkspaces();
      closeWsDialog();
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteWs) return;
    setDeleting(true);
    try {
      await deleteWorkspace(deleteWs.id);
      await refetchWorkspaces();
      if (activeWorkspaceId === deleteWs.id) {
        const remaining = workspaces.filter((w) => w.id !== deleteWs.id);
        if (remaining.length > 0) setActiveWorkspaceId(remaining[0].id);
      }
      setDeleteWs(null);
      setDeleteConfirm('');
    } finally {
      setDeleting(false);
    }
  };

  const handleCreateCp = async () => {
    if (!cpDialogWs || !newCpName.trim()) return;
    setCreatingCp(true);
    try {
      await createCheckpoint(cpDialogWs.id, {
        name: newCpName.trim(),
        checkpoint_at: `${newCpDate}T${newCpTime || '00:00'}:00`,
        note: newCpNote.trim() || undefined,
      });
      await refetchCheckpoints();
      setCpDialogWs(null);
      setNewCpName('');
      setNewCpNote('');
    } finally {
      setCreatingCp(false);
    }
  };

  const handleEditCp = async () => {
    if (!editCp || !editCpName.trim()) return;
    setSavingCp(true);
    try {
      await updateCheckpoint(editCpWsId, editCp.id, {
        name: editCpName.trim(),
        checkpoint_at: `${editCpDate}T${editCpTime || '00:00'}:00`,
        note: editCpNote.trim() || undefined,
      });
      await refetchCheckpoints();
      setEditCp(null);
    } finally {
      setSavingCp(false);
    }
  };

  const handleDeleteCp = async (wsId: number, cpId: number) => {
    await deleteCheckpoint(wsId, cpId);
    await refetchCheckpoints();
  };

  // Get checkpoints for a workspace (only active workspace checkpoints are loaded)
  const getWsCheckpoints = (wsId: number): Checkpoint[] => {
    if (wsId === activeWorkspaceId) return checkpoints;
    return [];
  };

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Workspaces</h1>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-xs">
            {workspaces.length} workspace{workspaces.length !== 1 ? 's' : ''}
          </Badge>
          <Button size="sm" className="h-7 text-xs" onClick={openCreate}>
            <Plus className="size-3.5 mr-1" />
            New Workspace
          </Button>
        </div>
      </div>

      {workspaces.map((ws) => {
        const isActive = ws.id === activeWorkspaceId;
        const wsCheckpoints = getWsCheckpoints(ws.id);

        return (
          <Card key={ws.id} className={`gap-0 py-0 ${isActive ? 'ring-1 ring-primary/40' : ''}`}>
            <CardContent className="p-4">
              {/* Header */}
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2.5 min-w-0">
                  <ColorDot color={ws.color} className="mt-0.5" />
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h2 className="font-semibold truncate">{ws.name}</h2>
                      {isActive && <Badge variant="secondary" className="text-[10px] h-4">Active</Badge>}
                    </div>
                    <div className="text-xs text-text-muted mt-0.5">
                      Hero: {ws.hero_username} · {ws.hand_count.toLocaleString()} hands
                      {ws.date_range.min && (
                        <> · {formatDate(ws.date_range.min)} – {formatDate(ws.date_range.max)}</>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  {!isActive && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs"
                      onClick={() => setActiveWorkspaceId(ws.id)}
                    >
                      Switch
                    </Button>
                  )}
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button size="sm" variant="ghost" className="h-7 w-7 p-0">
                        <Pencil className="size-3.5" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => openEdit(ws)}>
                        <Pencil className="size-3.5" />
                        Edit Workspace
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => {
                        const now = new Date();
                        setCpDialogWs(ws);
                        setNewCpName('');
                        setNewCpDate(now.toISOString().slice(0, 10));
                        setNewCpTime(`${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`);
                        setNewCpNote('');
                      }}>
                        <Bookmark className="size-3.5" />
                        Add Checkpoint
                      </DropdownMenuItem>
                      {workspaces.length > 1 && (
                        <DropdownMenuItem
                          variant="destructive"
                          onClick={() => { setDeleteWs(ws); setDeleteConfirm(''); }}
                        >
                          <Trash2 className="size-3.5" />
                          Delete Workspace
                        </DropdownMenuItem>
                      )}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>

              {/* Description */}
              {ws.description && (
                <p className="text-xs text-text-muted mt-2">{ws.description}</p>
              )}

              {/* Checkpoints */}
              {isActive && wsCheckpoints.length > 0 && (
                <>
                  <Separator className="my-3" />
                  <div className="space-y-1.5">
                    <div className="text-xs font-medium text-text-muted uppercase tracking-wide flex items-center gap-1.5">
                      <Bookmark className="size-3" />
                      Checkpoints ({wsCheckpoints.length})
                    </div>
                    {wsCheckpoints.map((cp) => (
                      <div
                        key={cp.id}
                        className="flex items-center justify-between text-xs py-1 px-2 rounded hover:bg-surface-hover group"
                      >
                        <div className="min-w-0">
                          <span className="font-medium">{cp.name}</span>
                          <span className="text-text-muted ml-1.5">{formatCheckpointDateTime(cp.checkpoint_at)}</span>
                          {cp.note && <span className="text-text-muted ml-1.5">— {cp.note}</span>}
                        </div>
                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-5 w-5 p-0"
                            onClick={() => {
                              const d = new Date(cp.checkpoint_at);
                              setEditCp(cp);
                              setEditCpWsId(ws.id);
                              setEditCpName(cp.name);
                              setEditCpDate(cp.checkpoint_at.slice(0, 10));
                              setEditCpTime(`${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`);
                              setEditCpNote(cp.note ?? '');
                            }}
                          >
                            <Pencil className="size-3" />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-5 w-5 p-0 text-red hover:text-red"
                            onClick={() => handleDeleteCp(ws.id, cp.id)}
                          >
                            <Trash2 className="size-3" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        );
      })}

      {/* Edit / Create Workspace Dialog */}
      <Dialog open={!!editWs || isCreating} onOpenChange={(open) => { if (!open) closeWsDialog(); }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{isCreating ? 'New Workspace' : 'Edit Workspace'}</DialogTitle>
            <DialogDescription>
              {isCreating ? 'Create a new workspace to keep hands separate.' : 'Update workspace settings.'}
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">Name</label>
              <Input
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                autoFocus
                onKeyDown={(e) => { if (e.key === 'Enter' && editName.trim()) handleSave(); }}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">Hero Username</label>
              <Input value={editHero} onChange={(e) => setEditHero(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">
                Description <span className="text-muted-foreground font-normal">(optional)</span>
              </label>
              <Textarea value={editDesc} onChange={(e) => setEditDesc(e.target.value)} rows={2} />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">Color</label>
              <div className="flex items-center gap-1.5">
                {PRESET_COLORS.map((c) => (
                  <button
                    key={c.label}
                    type="button"
                    onClick={() => setEditColor(c.value)}
                    className={`size-6 rounded-full border-2 transition-colors ${
                      editColor === c.value ? 'border-white ring-1 ring-primary' : 'border-transparent hover:border-muted-foreground/40'
                    }`}
                    style={{ backgroundColor: c.value ?? '#6b7280' }}
                    title={c.label}
                  />
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={closeWsDialog} disabled={saving}>Cancel</Button>
            <Button onClick={handleSave} disabled={!editName.trim() || saving}>
              {saving ? (isCreating ? 'Creating...' : 'Saving...') : (isCreating ? 'Create' : 'Save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Workspace Dialog */}
      <Dialog open={!!deleteWs} onOpenChange={(open) => { if (!open) { setDeleteWs(null); setDeleteConfirm(''); } }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Delete Workspace</DialogTitle>
            <DialogDescription>
              This will permanently delete <strong>{deleteWs?.name}</strong> and all its hands, stats, and checkpoints. This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium">
              Type <strong>{deleteWs?.name}</strong> to confirm
            </label>
            <Input
              value={deleteConfirm}
              onChange={(e) => setDeleteConfirm(e.target.value)}
              placeholder={deleteWs?.name}
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter' && deleteConfirm === deleteWs?.name) handleDelete();
              }}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setDeleteWs(null); setDeleteConfirm(''); }} disabled={deleting}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteConfirm !== deleteWs?.name || deleting}
            >
              {deleting ? 'Deleting...' : 'Delete Workspace'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* New Checkpoint Dialog */}
      <Dialog open={!!cpDialogWs} onOpenChange={(open) => { if (!open) setCpDialogWs(null); }}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle>New Checkpoint</DialogTitle>
            <DialogDescription>
              Add a checkpoint to {cpDialogWs?.name}.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-3 py-2">
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">Name</label>
              <Input
                value={newCpName}
                onChange={(e) => setNewCpName(e.target.value)}
                placeholder="e.g., Strategy Change"
                autoFocus
                onKeyDown={(e) => { if (e.key === 'Enter' && newCpName.trim()) handleCreateCp(); }}
              />
            </div>
            <div className="flex gap-3">
              <div className="flex flex-col gap-1.5 flex-1">
                <label className="text-sm font-medium">Date</label>
                <DatePicker
                  value={newCpDate}
                  onChange={(v) => setNewCpDate(v || new Date().toISOString().slice(0, 10))}
                  placeholder="Checkpoint date"
                  className="h-9 text-sm w-full"
                />
              </div>
              <div className="flex flex-col gap-1.5 w-24">
                <label className="text-sm font-medium">Time</label>
                <Input
                  type="time"
                  value={newCpTime}
                  onChange={(e) => setNewCpTime(e.target.value)}
                  className="h-9 text-sm"
                />
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">
                Note <span className="text-muted-foreground font-normal">(optional)</span>
              </label>
              <Input
                value={newCpNote}
                onChange={(e) => setNewCpNote(e.target.value)}
                placeholder="What changed?"
              />
            </div>
          </div>
          <DialogFooter>
            <Button onClick={handleCreateCp} disabled={!newCpName.trim() || creatingCp}>
              {creatingCp ? 'Creating...' : 'Create'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Checkpoint Dialog */}
      <Dialog open={!!editCp} onOpenChange={(open) => { if (!open) setEditCp(null); }}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle>Edit Checkpoint</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-3 py-2">
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">Name</label>
              <Input
                value={editCpName}
                onChange={(e) => setEditCpName(e.target.value)}
                autoFocus
                onKeyDown={(e) => { if (e.key === 'Enter' && editCpName.trim()) handleEditCp(); }}
              />
            </div>
            <div className="flex gap-3">
              <div className="flex flex-col gap-1.5 flex-1">
                <label className="text-sm font-medium">Date</label>
                <DatePicker
                  value={editCpDate}
                  onChange={(v) => setEditCpDate(v || editCpDate)}
                  placeholder="Checkpoint date"
                  className="h-9 text-sm w-full"
                />
              </div>
              <div className="flex flex-col gap-1.5 w-24">
                <label className="text-sm font-medium">Time</label>
                <Input
                  type="time"
                  value={editCpTime}
                  onChange={(e) => setEditCpTime(e.target.value)}
                  className="h-9 text-sm"
                />
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">
                Note <span className="text-muted-foreground font-normal">(optional)</span>
              </label>
              <Input
                value={editCpNote}
                onChange={(e) => setEditCpNote(e.target.value)}
                placeholder="What changed?"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditCp(null)} disabled={savingCp}>Cancel</Button>
            <Button onClick={handleEditCp} disabled={!editCpName.trim() || savingCp}>
              {savingCp ? 'Saving...' : 'Save'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
