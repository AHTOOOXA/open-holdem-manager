import { createContext, useContext, useState, useCallback, useEffect, useRef, type ReactNode } from 'react';
import { uploadFilesStream, importH2NStream, rebuildHands, getSettings, getHealth, clearDatabase, exportDb, importDb } from '@/lib/api';
import type { ImportResult, ImportProgress, Settings, HealthResponse } from '@/lib/api';
import { queryClient } from '@/lib/query-client';
import { toast } from 'sonner';
import { useWorkspace, type Workspace } from '@/contexts/WorkspaceContext';
import { createWorkspace, getWorkspaces } from '@/lib/api';
import {
  importCompletedMessage, importFailedMessage, importStartedMessage, rebuildCompletedMessage,
  type ImportKind, isZipBytes, totalHands,
} from '@/lib/import-ui';

const SAMPLE_WORKSPACE_NAME = 'Sample data';
const BUSY_TOAST = 'An import is already running';

type Phase = 'idle' | 'uploading' | 'rebuilding' | 'done' | 'error';

interface RebuildProgress {
  processed: number;
  total: number;
}

interface ImportState {
  phase: Phase;
  fileInfo: { count: number; size: number } | null;
  /** Set when importing from somewhere other than uploaded files, e.g. a Hand2Note database */
  sourceLabel: string | null;
  progress: ImportProgress | null;
  result: ImportResult | null;
  error: string | null;
  handCount: number;
  settings: Settings | null;
  autoRebuildProgress: RebuildProgress | null;
  /** What the running import reads from (drives the welcome view's stage line) */
  importKind: ImportKind;
  /** Workspace the running import writes into, null when no import is running */
  importWorkspaceId: number | null;
  /** True when that workspace had no hands when the import started */
  importWasEmpty: boolean;
}

interface ImportActions {
  startImport: (files: File[]) => void;
  startH2NImport: (path: string, name: string) => void;
  /** Switch to (or create) the sample workspace and import the bundled sample hands. */
  startSampleImport: () => Promise<void>;
  startRebuild: () => void;
  clearDb: () => Promise<void>;
  dismiss: () => void;
  refreshHandCount: () => Promise<void>;
  exportDatabase: () => Promise<void>;
  importDatabase: (file: File) => Promise<void>;
  showImportOverlay: boolean;
  setShowImportOverlay: (open: boolean) => void;
}

type ImportContextValue = ImportState & ImportActions;

const ImportContext = createContext<ImportContextValue | null>(null);

function useImport() {
  const ctx = useContext(ImportContext);
  if (!ctx) throw new Error('useImport must be used within ImportProvider');
  return ctx;
}

function ImportProvider({ children }: { children: ReactNode }) {
  const [phase, setPhase] = useState<Phase>('idle');
  const [fileInfo, setFileInfo] = useState<{ count: number; size: number } | null>(null);
  const [sourceLabel, setSourceLabel] = useState<string | null>(null);
  const [progress, setProgress] = useState<ImportProgress | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [handCount, setHandCount] = useState(0);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [showImportOverlay, setShowImportOverlay] = useState(false);
  const [autoRebuildProgress, setAutoRebuildProgress] = useState<RebuildProgress | null>(null);
  const rebuildPollRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const stoppedRef = useRef(false);
  const rebuildTotalRef = useRef(0);
  const importInFlightRef = useRef(false);
  const [importKind, setImportKind] = useState<ImportKind>('files');
  const [target, setTarget] = useState<{ id: number; wasEmpty: boolean } | null>(null);

  const { workspaces, activeWorkspace, activeWorkspaceId, setActiveWorkspaceId, refetchWorkspaces } = useWorkspace();
  // Latest workspace state for callbacks that must not re-create on every change
  const workspacesRef = useRef<Workspace[]>(workspaces);
  workspacesRef.current = workspaces;
  const activeRef = useRef({ id: activeWorkspaceId, handCount: activeWorkspace?.hand_count ?? 0 });
  activeRef.current = { id: activeWorkspaceId, handCount: activeWorkspace?.hand_count ?? 0 };
  const setActiveRef = useRef(setActiveWorkspaceId);
  setActiveRef.current = setActiveWorkspaceId;
  const refetchWorkspacesRef = useRef(refetchWorkspaces);
  refetchWorkspacesRef.current = refetchWorkspaces;

  const startRebuildPolling = useCallback((initialProgress?: RebuildProgress) => {
    setPhase('rebuilding');
    if (initialProgress) {
      setAutoRebuildProgress(initialProgress);
      rebuildTotalRef.current = initialProgress.total;
    }

    if (rebuildPollRef.current) clearTimeout(rebuildPollRef.current);
    stoppedRef.current = false;
    // setTimeout chain: the next tick is only scheduled after the previous one finished,
    // so two ticks can never both observe "done".
    const tick = async () => {
      let again = true;
      try {
        const h = await getHealth();
        if (stoppedRef.current) return;
        setHandCount(h.hands);
        if (h.rebuilding) {
          if (h.rebuild_progress) rebuildTotalRef.current = h.rebuild_progress.total;
          setAutoRebuildProgress(h.rebuild_progress ?? null);
        } else {
          again = false;
          rebuildPollRef.current = null;
          setPhase('idle');
          setAutoRebuildProgress(null);
          queryClient.invalidateQueries();
          const m = rebuildCompletedMessage(rebuildTotalRef.current || totalHands(workspacesRef.current) || h.hands);
          toast.success(m.title, { description: m.description });
        }
      } catch {
        // ignore transient errors
      }
      if (again && !stoppedRef.current) rebuildPollRef.current = setTimeout(tick, 1000);
    };
    rebuildPollRef.current = setTimeout(tick, 1000);
  }, []);

  useEffect(() => {
    getSettings().then(setSettings).catch(() => {});
    getHealth().then((h: HealthResponse) => {
      setHandCount(h.hands);
      if (h.rebuilding) {
        startRebuildPolling(h.rebuild_progress ?? undefined);
      }
    }).catch(() => {});

    return () => {
      stoppedRef.current = true;
      if (rebuildPollRef.current) clearTimeout(rebuildPollRef.current);
      rebuildPollRef.current = null;
    };
  }, [startRebuildPolling]);

  const refreshHandCount = useCallback(async () => {
    const h = await getHealth();
    setHandCount(h.hands);
  }, []);

  /** Common tail of every import: refresh counts + workspaces, toast, back to idle. */
  const finishImport = useCallback(async (res: ImportResult | null, err: unknown) => {
    if (res) setResult(res);
    else setError(err instanceof Error ? err.message : 'Import failed');
    await refreshHandCount().catch(() => {});
    queryClient.invalidateQueries();
    // Wait for fresh per-workspace hand counts so the welcome view doesn't flash back.
    await refetchWorkspacesRef.current().catch(() => {});
    setPhase('idle');
    setProgress(null);
    setFileInfo(null);
    setTarget(null);
    const msg = res ? importCompletedMessage(res) : importFailedMessage(err instanceof Error ? err.message : null);
    if (msg.kind === 'error') toast.error(msg.title, { description: msg.description });
    else if (msg.kind === 'success') toast.success(msg.title, { description: msg.description });
    else toast(msg.title, { description: msg.description });
  }, [refreshHandCount]);

  const beginImport = useCallback((kind: ImportKind, ws: { id: number; handCount: number }, started: string | null) => {
    setImportKind(kind);
    setTarget({ id: ws.id, wasEmpty: ws.handCount === 0 });
    setPhase('uploading');
    setError(null);
    setResult(null);
    setProgress(null);
    setShowImportOverlay(false);
    if (ws.handCount > 0 && started) toast(importStartedMessage(kind, 0).title, { description: started });
  }, []);

  /** Runs an upload. The caller already owns importInFlightRef. */
  const runFileImport = useCallback(async (files: File[], ws: { id: number; handCount: number }, kind: ImportKind) => {
    const validFiles = files.filter(
      (f) => f.name.endsWith('.txt') || f.name.endsWith('.zip')
    );
    if (validFiles.length === 0) {
      setPhase('idle');
      toast.error('Import failed', { description: 'Please upload .txt or .zip hand history files' });
      return;
    }

    const totalSize = validFiles.reduce((sum, f) => sum + f.size, 0);
    setFileInfo({ count: validFiles.length, size: totalSize });
    setSourceLabel(kind === 'sample' ? 'sample data' : null);
    beginImport(kind, ws, importStartedMessage(kind, validFiles.length).description);

    try {
      const res = await uploadFilesStream(validFiles, (p) => setProgress(p));
      await finishImport(res, null);
    } catch (e) {
      await finishImport(null, e);
    }
  }, [beginImport, finishImport]);

  /** Claims the single import slot synchronously; false (with a toast) if one is running. */
  const claimImport = useCallback((): boolean => {
    if (importInFlightRef.current) {
      toast(BUSY_TOAST);
      return false;
    }
    importInFlightRef.current = true;
    return true;
  }, []);

  const startImport = useCallback(async (files: File[]) => {
    if (!claimImport()) return;
    setPhase('uploading');
    try {
      await runFileImport(files, activeRef.current, 'files');
    } finally {
      importInFlightRef.current = false;
    }
  }, [claimImport, runFileImport]);

  const startSampleImport = useCallback(async () => {
    if (!claimImport()) return;
    setPhase('uploading');
    setProgress(null);
    let started = false;
    try {
      // Fetch and validate first: nothing is created or switched if the bundle is missing.
      const url = new URL('sample/ohm-sample-hands.zip', new URL(import.meta.env.BASE_URL, window.location.origin));
      let blob: Blob | null = null;
      let ws = workspacesRef.current.find((w) => w.name === SAMPLE_WORKSPACE_NAME);
      if (!ws) {
        // The list may be stale (e.g. created in another session)
        ws = (await getWorkspaces()).find((w) => w.name === SAMPLE_WORKSPACE_NAME);
      }
      if (!ws || ws.hand_count === 0) {
        const resp = await fetch(url);
        const ct = resp.headers.get('content-type') ?? '';
        const head = resp.ok && !ct.includes('text/html') ? await resp.blob() : null;
        if (!head || !isZipBytes(new Uint8Array(await head.slice(0, 2).arrayBuffer()))) {
          toast.error('Sample data not found', { description: 'The bundled sample hands could not be loaded.' });
          setPhase('idle');
          return;
        }
        blob = head;
      }
      if (!ws) {
        ws = await createWorkspace({ name: SAMPLE_WORKSPACE_NAME, description: 'Bundled sample: 2,000 GGPoker hands' });
      }
      // Writes the id to localStorage synchronously: the upload below picks it up as workspace_id.
      setActiveRef.current(ws.id);
      await refetchWorkspacesRef.current();
      if (!blob) {
        setPhase('idle');
        toast('Switched to sample data');
        return;
      }
      started = true;
      const file = new File([blob], 'ohm-sample-hands.zip', { type: 'application/zip' });
      await runFileImport([file], { id: ws.id, handCount: 0 }, 'sample');
    } catch (e) {
      if (!started) setPhase('idle');
      toast.error('Sample data failed', { description: e instanceof Error ? e.message : 'Unknown error' });
    } finally {
      importInFlightRef.current = false;
    }
  }, [claimImport, runFileImport]);

  const startH2NImport = useCallback(async (path: string, name: string) => {
    if (!claimImport()) return;
    const ws = activeRef.current;
    setFileInfo(null);
    setSourceLabel(`Hand2Note database "${name}"`);
    beginImport('h2n', ws, importStartedMessage('h2n', 0, `Hand2Note database "${name}"`).description);
    try {
      const res = await importH2NStream(path, (p) => setProgress(p));
      await finishImport(res, null);
    } catch (e) {
      await finishImport(null, e);
    } finally {
      importInFlightRef.current = false;
    }
  }, [claimImport, beginImport, finishImport]);

  const startRebuild = useCallback(async () => {
    if (importInFlightRef.current || rebuildPollRef.current) {
      toast(BUSY_TOAST);
      return;
    }

    try {
      const res = await rebuildHands();
      if (res.status === 'already_running' || res.status === 'started') {
        startRebuildPolling(res.total ? { processed: 0, total: res.total } : undefined);
      }
      // 'empty' — nothing to do
    } catch (e) {
      toast.error('Rebuild failed', { description: e instanceof Error ? e.message : 'Unknown error' });
    }
  }, [startRebuildPolling]);

  const clearDb = useCallback(async () => {
    await clearDatabase();
    await refreshHandCount();
    setResult(null);
    queryClient.invalidateQueries();
  }, [refreshHandCount]);

  const dismiss = useCallback(() => {
    setPhase('idle');
    setProgress(null);
    setFileInfo(null);
    setResult(null);
    setError(null);
  }, []);

  const exportDatabase = useCallback(async () => {
    await exportDb();
  }, []);

  const importDatabase = useCallback(async (file: File) => {
    const res = await importDb(file);
    setHandCount(res.hands);
    queryClient.invalidateQueries();
  }, []);

  return (
    <ImportContext.Provider
      value={{
        phase, fileInfo, sourceLabel, progress, result, error, handCount, settings,
        autoRebuildProgress, importKind,
        importWorkspaceId: target?.id ?? null, importWasEmpty: target?.wasEmpty ?? false,
        startImport, startH2NImport, startSampleImport, startRebuild, clearDb, dismiss, refreshHandCount,
        exportDatabase, importDatabase, showImportOverlay, setShowImportOverlay,
      }}
    >
      {children}
    </ImportContext.Provider>
  );
}

export { useImport, ImportProvider };
