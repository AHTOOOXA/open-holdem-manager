import { useState } from 'react';
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
  const matches = confirm === workspace.name;

  const run = async () => {
    if (!matches) return;
    setDeleting(true);
    try {
      await deleteWorkspace(workspace.id);
      await onDeleted();
      onClose();
    } finally {
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
