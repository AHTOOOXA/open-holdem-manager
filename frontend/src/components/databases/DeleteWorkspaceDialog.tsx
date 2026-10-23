import { useRef, useState } from 'react';
import { toast } from 'sonner';
import { deleteWorkspace } from '@/lib/api';
import type { Workspace } from '@/contexts/WorkspaceContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';

interface Props {
  workspace: Workspace;
  onClose: () => void;
  onDeleted: () => Promise<void>;
}

/** Type-to-confirm delete. Mount only while open. */
export default function DeleteWorkspaceDialog({ workspace, onClose, onDeleted }: Props) {
  const [confirm, setConfirm] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const busyRef = useRef(false);
  const matches = confirm === workspace.name;

  const run = async () => {
    if (!matches || busyRef.current) return;
    busyRef.current = true;
    setDeleting(true);
    setError(null);
    try {
      await deleteWorkspace(workspace.id);
      await onDeleted();
      onClose();
    } catch (e) {
      const msg = e instanceof Error && e.message ? e.message : 'Could not delete the workspace';
      setError(msg);
      toast.error('Delete failed', { description: msg });
    } finally {
      busyRef.current = false;
      setDeleting(false);
    }
  };

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Delete workspace</DialogTitle>
          <DialogDescription>
            This will permanently delete <strong>{workspace.name}</strong> and all its hands, stats, and checkpoints. This cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium">
            Type <strong>{workspace.name}</strong> to confirm
          </label>
          <Input
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            placeholder={workspace.name}
            autoFocus
            onKeyDown={(e) => { if (e.key === 'Enter') void run(); }}
          />
          {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={deleting}>Cancel</Button>
          <Button variant="destructive" onClick={run} disabled={!matches || deleting}>
            {deleting ? 'Deleting...' : 'Delete workspace'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
