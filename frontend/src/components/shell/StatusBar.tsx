import { useEffect, useRef, useState } from 'react';
import { Progress } from '@/components/ui/progress';
import WorkspaceSwitcher from '@/components/WorkspaceSwitcher';
import { useLocation } from 'react-router-dom';
import { useImport } from '@/contexts/ImportContext';
import { useWorkspace } from '@/contexts/WorkspaceContext';
import { getElectronAPI } from '@/lib/electron';
import { Button } from '@/components/ui/button';
import type { ImportProgress } from '@/lib/api';
import { progressParts, stageLabel } from '@/lib/import-ui';
import AutoImportIndicator from './AutoImportIndicator';
import UpdateNotice from './UpdateNotice';
import { useUpdateState } from './useUpdateState';

/** Exact counts in progress lines (1,234/5,000), not the shortened 1.2k. */
const count = (v: number) => v.toLocaleString();

function percentOf(processed: number | undefined, total: number | undefined): number {
  return total && total > 0 ? Math.round(((processed ?? 0) / total) * 100) : 0;
}

function ActivityBar({ value, label }: { value: number; label: string }) {
  return <Progress value={value} aria-label={label} className="h-1 w-24 shrink-0 sm:w-32" />;
}

function ImportActivity({ progress }: { progress: ImportProgress | null }) {
  const { importKind, cancelImport, canCancelImport, cancelling } = useImport();
  const total = progress?.total ?? progress?.total_hands;
  const processed = progress?.processed ?? 0;
  const parts = progressParts(progress);
  const text = cancelling ? 'cancelling…' : parts.length > 0 ? parts.join(', ') : 'preparing…';

  return (
    <div className="flex min-w-0 items-center gap-2 px-1">
      <span className="truncate">
        <span className="text-foreground">{stageLabel(importKind).replace(/…$/, '')}:</span> {text}
      </span>
      <ActivityBar value={percentOf(processed, total)} label="Import progress" />
      <Button variant="ghost" size="xs" className="shrink-0" disabled={!canCancelImport} onClick={cancelImport}>
        Cancel
      </Button>
    </div>
  );
}

function RebuildActivity({ progress }: { progress: { processed: number; total: number } | null }) {
  const [hps, setHps] = useState(0);
  const prevRef = useRef<{ processed: number; time: number } | null>(null);

  useEffect(() => {
    if (!progress) return;
    const now = Date.now();
    const prev = prevRef.current;
    if (prev) {
      const dt = (now - prev.time) / 1000;
      const dp = progress.processed - prev.processed;
      if (dt > 0 && dp > 0) setHps(Math.round(dp / dt));
    }
    prevRef.current = { processed: progress.processed, time: now };
  }, [progress]);

  return (
    <div className="flex min-w-0 items-center gap-2 px-1">
      <span className="truncate">
        <span className="text-foreground">Rebuilding statistics:</span>{' '}
        {progress ? `${count(progress.processed)}/${count(progress.total)} hands` : 'starting…'}
        {hps > 0 && `, ${count(hps)} h/s`}
      </span>
      <ActivityBar value={percentOf(progress?.processed, progress?.total)} label="Rebuild progress" />
    </div>
  );
}

function useAppVersion(): string {
  const [version, setVersion] = useState(__APP_VERSION__);
  useEffect(() => {
    const get = getElectronAPI()?.getAppVersion;
    if (!get) return;
    get().then((v) => v && setVersion(v)).catch(() => {});
  }, []);
  return version;
}

/**
 * Bottom row of the content column. Left: what the app is doing (import, then rebuild, then an
 * available update; first match wins). Right: workspace selector and app version.
 */
export default function StatusBar() {
  const { phase, progress, autoRebuildProgress, importWasEmpty, importWorkspaceId } = useImport();
  const { activeWorkspaceId } = useWorkspace();
  const { pathname } = useLocation();
  const update = useUpdateState();
  const version = useAppVersion();

  // While importing into an empty workspace, Reports/Statistics/Sessions show the progress in the
  // welcome view; don't repeat it here
  const welcomeShowsProgress =
    importWasEmpty && importWorkspaceId === activeWorkspaceId && /^\/(reports|statistics|sessions)(\/|$)/.test(pathname);
  const importing = phase === 'uploading' && !welcomeShowsProgress;
  const rebuilding = phase === 'rebuilding' || autoRebuildProgress != null;
  // The workspace selector hides during any import, even one only the welcome view shows
  const busy = phase === 'uploading' || rebuilding;

  let activity = null;
  if (importing) {
    activity = <ImportActivity progress={progress} />;
  } else if (rebuilding) {
    activity = <RebuildActivity progress={autoRebuildProgress} />;
  } else if (update.version && !update.dismissed) {
    activity = <UpdateNotice update={update} />;
  }

  return (
    <footer
      aria-label="Status bar"
      className="sticky bottom-0 z-(--z-sticky) flex h-(--shell-status-h) shrink-0 items-center gap-3 border-t border-border bg-background px-2 text-xs text-muted-foreground"
    >
      <div className="flex min-w-0 flex-1 items-center gap-3">
        {activity}
        <AutoImportIndicator />
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {!busy && <WorkspaceSwitcher variant="statusbar" />}
        <span className="tabular-nums text-subtle-foreground">OHM v{version}</span>
      </div>
    </footer>
  );
}
