import { createContext, useContext, useState, useCallback, useEffect, useRef, type ReactNode } from 'react';
import { uploadFilesStream, importH2NStream, rebuildHands, getSettings, getHealth, clearDatabase, exportDb, importDb } from '@/lib/api';
import type { ImportResult, ImportProgress, Settings, HealthResponse } from '@/lib/api';
import { queryClient } from '@/lib/query-client';

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
  const rebuildPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startRebuildPolling = useCallback((initialProgress?: RebuildProgress) => {
    setPhase('rebuilding');
    if (initialProgress) setAutoRebuildProgress(initialProgress);

    if (rebuildPollRef.current) clearInterval(rebuildPollRef.current);
    rebuildPollRef.current = setInterval(async () => {
      try {
        const h = await getHealth();
        setHandCount(h.hands);
        if (h.rebuilding) {
          setAutoRebuildProgress(h.rebuild_progress ?? null);
        } else {
          if (rebuildPollRef.current) clearInterval(rebuildPollRef.current);
          rebuildPollRef.current = null;
          setPhase('idle');
          setAutoRebuildProgress(null);
          queryClient.invalidateQueries();
        }
      } catch {
        // ignore transient errors
      }
    }, 1000);
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
      if (rebuildPollRef.current) clearInterval(rebuildPollRef.current);
    };
  }, [startRebuildPolling]);

  const refreshHandCount = useCallback(async () => {
    const h = await getHealth();
    setHandCount(h.hands);
  }, []);

  const startImport = useCallback(async (files: File[]) => {
    if (phase !== 'idle') return;

    const validFiles = files.filter(
      (f) => f.name.endsWith('.txt') || f.name.endsWith('.zip')
    );
    if (validFiles.length === 0) {
      setError('Please upload .txt or .zip hand history files');
      setPhase('error');
      return;
    }

    const totalSize = validFiles.reduce((sum, f) => sum + f.size, 0);
    setFileInfo({ count: validFiles.length, size: totalSize });
    setSourceLabel(null);
    setPhase('uploading');
    setError(null);
    setResult(null);
    setProgress(null);

    try {
      const res = await uploadFilesStream(validFiles, (p) => setProgress(p));
      setResult(res);
      setPhase('done');
      await refreshHandCount();
      queryClient.invalidateQueries();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed');
      setPhase('error');
      await refreshHandCount().catch(() => {});
      queryClient.invalidateQueries();
    }
  }, [phase, refreshHandCount]);

  // Stub: implemented by the welcome-view track
  const startSampleImport = useCallback(async () => {}, []);

  const startH2NImport = useCallback(async (path: string, name: string) => {
    if (phase !== 'idle') return;
    setFileInfo(null);
    setSourceLabel(`Hand2Note database "${name}"`);
    setPhase('uploading');
    setError(null);
    setResult(null);
    setProgress(null);
    try {
      const res = await importH2NStream(path, (p) => setProgress(p));
      setResult(res);
      setPhase('done');
      await refreshHandCount();
      queryClient.invalidateQueries();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Import failed');
      setPhase('error');
      await refreshHandCount().catch(() => {});
      queryClient.invalidateQueries();
    }
  }, [phase, refreshHandCount]);

  const startRebuild = useCallback(async () => {
    if (phase !== 'idle') return;

    try {
      const res = await rebuildHands();
      if (res.status === 'already_running' || res.status === 'started') {
        startRebuildPolling(res.total ? { processed: 0, total: res.total } : undefined);
      }
      // 'empty' — nothing to do
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Rebuild failed');
      setPhase('error');
    }
  }, [phase, startRebuildPolling]);

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
        autoRebuildProgress,
        startImport, startH2NImport, startSampleImport, startRebuild, clearDb, dismiss, refreshHandCount,
        exportDatabase, importDatabase, showImportOverlay, setShowImportOverlay,
      }}
    >
      {children}
    </ImportContext.Provider>
  );
}

export { useImport, ImportProvider };
