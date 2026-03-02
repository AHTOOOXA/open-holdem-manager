import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getWorkspaces, getCheckpoints } from '@/lib/api';

export interface Workspace {
  id: number;
  name: string;
  hero_username: string;
  hero_site: string;
  description: string | null;
  color: string | null;
  hand_count: number;
  date_range: { min: string | null; max: string | null };
  created_at: string;
}

export interface Checkpoint {
  id: number;
  workspace_id: number;
  name: string;
  checkpoint_at: string;
  note: string | null;
  created_at: string;
}

interface WorkspaceContextValue {
  workspaces: Workspace[];
  activeWorkspaceId: number;
  activeWorkspace: Workspace | null;
  checkpoints: Checkpoint[];
  setActiveWorkspaceId: (id: number) => void;
  refetchWorkspaces: () => Promise<void>;
  refetchCheckpoints: () => Promise<void>;
}

const WS_STORAGE_KEY = 'ohm_active_workspace_id';

function getStoredWorkspaceId(): number {
  try {
    const val = localStorage.getItem(WS_STORAGE_KEY);
    if (val) {
      const parsed = parseInt(val, 10);
      if (!isNaN(parsed)) return parsed;
    }
  } catch {
    // localStorage unavailable
  }
  return 1;
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

function useWorkspace() {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error('useWorkspace must be used within WorkspaceProvider');
  return ctx;
}

function WorkspaceProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [activeWorkspaceId, setActiveId] = useState(getStoredWorkspaceId);

  // Clean up stale view localStorage key
  try { localStorage.removeItem('ohm_active_view_id'); } catch { /* noop */ }

  const workspacesQuery = useQuery({
    queryKey: ['workspaces'],
    queryFn: getWorkspaces,
  });

  const checkpointsQuery = useQuery({
    queryKey: ['checkpoints', activeWorkspaceId],
    queryFn: () => getCheckpoints(activeWorkspaceId),
  });

  const workspaces = workspacesQuery.data ?? [];
  const activeWorkspace = workspaces.find((w) => w.id === activeWorkspaceId) ?? null;
  const checkpoints = checkpointsQuery.data ?? [];

  const setActiveWorkspaceId = useCallback((id: number) => {
    try {
      localStorage.setItem(WS_STORAGE_KEY, String(id));
    } catch {
      // localStorage unavailable
    }
    setActiveId(id);
    queryClient.invalidateQueries();
  }, [queryClient]);

  const refetchWorkspaces = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ['workspaces'] });
  }, [queryClient]);

  const refetchCheckpoints = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ['checkpoints', activeWorkspaceId] });
  }, [queryClient, activeWorkspaceId]);

  return (
    <WorkspaceContext.Provider
      value={{
        workspaces,
        activeWorkspaceId,
        activeWorkspace,
        checkpoints,
        setActiveWorkspaceId,
        refetchWorkspaces,
        refetchCheckpoints,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
}

export { useWorkspace, WorkspaceProvider };
