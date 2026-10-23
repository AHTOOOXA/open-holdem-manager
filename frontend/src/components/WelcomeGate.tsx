import type { ReactNode } from 'react';
import { FolderUp, Database, FlaskConical } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { useImport } from '@/contexts/ImportContext';
import { useWorkspace } from '@/contexts/WorkspaceContext';
import { progressLine, progressPct, stageLabel, welcomeState } from '@/lib/import-ui';

/**
 * Wraps Reports, Statistics and Sessions: shows the welcome view instead of the page while the
 * active workspace has no hands, and the import progress while an import into it is running.
 */
export default function WelcomeGate({ children }: { children: ReactNode }) {
  const { activeWorkspace, activeWorkspaceId } = useWorkspace();
  const { phase, progress, importKind, importWorkspaceId, importWasEmpty, setShowImportOverlay, startSampleImport } = useImport();

  const state = welcomeState({
    handCount: activeWorkspace ? activeWorkspace.hand_count : null,
    phase,
    importingIntoActive: importWasEmpty && importWorkspaceId === activeWorkspaceId,
  });

  if (state === 'content') return <>{children}</>;

  return (
    <div className="mx-auto mt-24 flex flex-col items-center gap-4 text-center">
      <div className="flex size-16 items-center justify-center rounded-full bg-muted text-3xl text-muted-foreground" aria-hidden>
        ♠
      </div>

      {state === 'progress' ? (
        <div className="flex min-w-[400px] flex-col gap-3">
          <p className="text-lg font-medium">{stageLabel(importKind)}</p>
          <Progress value={progressPct(progress)} className="h-2" />
          <p className="text-sm text-muted-foreground tabular-nums">{progressLine(progress) || 'Preparing…'}</p>
        </div>
      ) : (
        <>
          <h1 className="text-2xl font-semibold">Welcome to Open Holdem Manager</h1>
          <p className="text-muted-foreground">
            Import your hand histories to see your stats. Everything stays on this computer.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-2">
            <Button onClick={() => setShowImportOverlay(true)}>
              <FolderUp /> Import hand histories
            </Button>
            <Button variant="outline" onClick={() => setShowImportOverlay(true)}>
              <Database /> Import from Hand2Note
            </Button>
            <Button variant="ghost" onClick={() => void startSampleImport()}>
              <FlaskConical /> Use sample data
            </Button>
          </div>
          <p className="text-sm text-muted-foreground">You can also drop .txt or .zip files anywhere.</p>
          <p className="max-w-md text-xs text-muted-foreground">
            GGPoker players: close the GG client before running OHM. It is for review after your session.
          </p>
        </>
      )}
    </div>
  );
}
