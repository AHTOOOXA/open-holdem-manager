/**
 * Statistics screen (/statistics): the workspace's dashboard tree on the left, the shown
 * dashboard (header + pages) on the right. The tree document (structure, definitions, selected
 * dashboard, panel width / collapsed) is stored by the backend per workspace; pages, selections
 * and results live in memory.
 */
import { useState } from 'react';
import { RefreshCw } from 'lucide-react';
import DashboardTree from '@/components/statistics/DashboardTree';
import DashboardView from '@/components/statistics/DashboardView';
import { useDashboardsDoc } from '@/components/statistics/useDashboardsDoc';
import { Button } from '@/components/ui/button';
import { useWorkspace } from '@/contexts/WorkspaceContext';
import {
  canDelete, cloneDashboard, deleteNode, findDashboard, selectDashboard, setCollapsed, setDefinition,
} from '@/lib/statistics/tree';

export default function StatisticsPage() {
  const { activeWorkspaceId } = useWorkspace();
  // A workspace switch drops the in-memory tree state (undo stack, search, ...)
  return <StatisticsScreen key={activeWorkspaceId} workspaceId={activeWorkspaceId} />;
}

function StatisticsScreen({ workspaceId }: { workspaceId: number }) {
  const d = useDashboardsDoc(workspaceId);
  const doc = d.doc;
  // Clone from the gear menu starts the inline rename in the tree, like the tree's own Clone
  const [renameRequest, setRenameRequest] = useState<{ id: number; rev: number } | null>(null);

  if (!doc) {
    return (
      <div className="flex h-full min-h-0 items-start p-6">
        {d.error ? (
          <div role="alert" className="flex flex-col items-start gap-3">
            <p className="text-sm text-foreground">Could not load the dashboards.</p>
            <p className="text-sm text-muted-foreground">{d.error.message}</p>
            <Button variant="outline" size="sm" onClick={d.refetch}>
              <RefreshCw /> Retry
            </Button>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Loading…</p>
        )}
      </div>
    );
  }

  const shown = findDashboard(doc, doc.config.selected_id);
  const collapsed = doc.config.collapsed;

  return (
    // -m-4 + the shell's height: the screen fills the content area edge to edge and scrolls inside
    <div className="-m-4 flex h-[calc(100svh-var(--shell-header-h)-var(--shell-status-h))] min-h-0 min-w-0 bg-surface-sunken [contain:inline-size]">
      {!collapsed && (
        <DashboardTree
          workspaceId={workspaceId}
          doc={doc}
          commit={d.commit}
          onShow={(id) => d.commit(selectDashboard(doc, id))}
          onCollapse={() => d.commit(setCollapsed(doc, true))}
          canUndo={d.canUndo}
          canRedo={d.canRedo}
          onUndo={d.undo}
          onRedo={d.redo}
          renameRequest={renameRequest}
        />
      )}
      {shown ? (
        <DashboardView
          key={shown.id}
          workspaceId={workspaceId}
          dashboard={shown}
          onDefinitionChange={(def) => d.commit(setDefinition(doc, shown.id, def))}
          treeCollapsed={collapsed}
          onExpandTree={() => d.commit(setCollapsed(doc, false))}
          canDelete={canDelete(doc, shown.id)}
          onDelete={() => d.commit(deleteNode(doc, shown.id), { undoable: true })}
          onClone={() => {
            const r = cloneDashboard(doc, shown.id);
            if (!r) return;
            d.commit(r.doc, { undoable: true });
            setRenameRequest((q) => ({ id: r.id, rev: (q?.rev ?? 0) + 1 }));
          }}
        />
      ) : (
        <p className="p-6 text-sm text-muted-foreground">No dashboard selected.</p>
      )}
    </div>
  );
}
