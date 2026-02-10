import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from 'react';
import { uploadFilesStream, rebuildHands, getSettings, updateSettings, getHealth, clearDatabase } from '@/lib/api';
import type { ImportResult, ImportProgress, Settings } from '@/lib/api';
import { queryClient } from '@/lib/query-client';

type Phase = 'idle' | 'uploading' | 'rebuilding' | 'done' | 'error';

interface ImportState {
  phase: Phase;
  fileInfo: { count: number; size: number } | null;
  progress: ImportProgress | null;
  result: ImportResult | null;
  error: string | null;
  handCount: number;
  settings: Settings | null;
}

interface ImportActions {
  startImport: (files: File[]) => void;
  startRebuild: () => void;
  clearDb: () => Promise<void>;
  dismiss: () => void;
  updateHeroName: (name: string) => Promise<void>;
  refreshHandCount: () => Promise<void>;
  importPopoverOpen: boolean;
  setImportPopoverOpen: (open: boolean) => void;
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
  const [progress, setProgress] = useState<ImportProgress | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [handCount, setHandCount] = useState(0);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [importPopoverOpen, setImportPopoverOpen] = useState(false);

  useEffect(() => {
    getSettings().then(setSettings).catch(() => {});
    getHealth().then((h) => setHandCount(h.hands)).catch(() => {});
  }, []);

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
    }
  }, [phase, refreshHandCount]);

  const startRebuild = useCallback(async () => {
    if (phase !== 'idle') return;

    setPhase('rebuilding');
    setError(null);
    setResult(null);
    setProgress(null);
    setFileInfo(null);

    try {
      const res = await rebuildHands((p) => setProgress(p));
      setResult(res);
      setPhase('done');
      await refreshHandCount();
      queryClient.invalidateQueries();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Rebuild failed');
      setPhase('error');
    }
  }, [phase, refreshHandCount]);

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

  const updateHeroName = useCallback(async (name: string) => {
    const updated = await updateSettings({
      hero_username: name,
      hero_site: settings?.hero_site || 'GG',
    });
    setSettings(updated);
    queryClient.invalidateQueries();
  }, [settings]);

  return (
    <ImportContext.Provider
      value={{
        phase, fileInfo, progress, result, error, handCount, settings,
        startImport, startRebuild, clearDb, dismiss, updateHeroName, refreshHandCount,
        importPopoverOpen, setImportPopoverOpen,
      }}
    >
      {children}
    </ImportContext.Provider>
  );
}

export { useImport, ImportProvider };
