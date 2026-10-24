import { useState } from 'react';
import { Plus } from 'lucide-react';
import { useWorkspace } from '@/contexts/WorkspaceContext';
import type { Workspace } from '@/contexts/WorkspaceContext';
import { Button } from '@/components/ui/button';
import WorkspaceList from '@/components/databases/WorkspaceList';
import WorkspaceFormDialog from '@/components/databases/WorkspaceFormDialog';
import DeleteWorkspaceDialog from '@/components/databases/DeleteWorkspaceDialog';
import CheckpointsDialog from '@/components/databases/CheckpointsDialog';
import DataFolderPanel from '@/components/databases/DataFolderPanel';
import DatabaseFilePanel from '@/components/databases/DatabaseFilePanel';

export default function DatabasesPage() {
  const { workspaces, activeWorkspaceId, setActiveWorkspaceId, refetchWorkspaces } = useWorkspace();
  const [form, setForm] = useState<{ workspace: Workspace | null } | null>(null);
  const [deleting, setDeleting] = useState<Workspace | null>(null);
  const [checkpointsFor, setCheckpointsFor] = useState<Workspace | null>(null);

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold">Databases</h1>
          <p className="text-sm text-muted-foreground">
            Each workspace is a separate set of hands and stats. Switching is instant.
          </p>
        </div>
        <Button size="sm" onClick={() => setForm({ workspace: null })}>
          <Plus className="size-3.5" />
          Create workspace
        </Button>
      </div>

      <WorkspaceList
        workspaces={workspaces}
        activeId={activeWorkspaceId}
        onSelect={setActiveWorkspaceId}
        onEdit={(ws) => setForm({ workspace: ws })}
        onCheckpoints={setCheckpointsFor}
        onDelete={setDeleting}
      />

      <DataFolderPanel />

      <DatabaseFilePanel />

      {form && (
        <WorkspaceFormDialog
          key={form.workspace?.id ?? 'new'}
          workspace={form.workspace}
          onClose={() => setForm(null)}
          onSaved={refetchWorkspaces}
        />
      )}
      {deleting && (
        <DeleteWorkspaceDialog
          workspace={deleting}
          onClose={() => setDeleting(null)}
          onDeleted={refetchWorkspaces}
        />
      )}
      {checkpointsFor && <CheckpointsDialog workspace={checkpointsFor} onClose={() => setCheckpointsFor(null)} />}
    </div>
  );
}
