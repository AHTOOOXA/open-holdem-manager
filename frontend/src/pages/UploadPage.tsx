import { useState, useCallback, useEffect } from 'react';
import { uploadFilesStream, rebuildHands, getSettings, updateSettings, getHealth, clearDatabase } from '@/lib/api';
import type { ImportResult, ImportProgress, Settings } from '@/lib/api';

export default function UploadPage() {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState<ImportProgress | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [editingName, setEditingName] = useState(false);
  const [nameInput, setNameInput] = useState('');
  const [handCount, setHandCount] = useState(0);
  const [fileInfo, setFileInfo] = useState<{ count: number; size: number } | null>(null);

  useEffect(() => {
    getSettings().then(setSettings);
    getHealth().then((h) => setHandCount(h.hands));
  }, []);

  const handleFiles = useCallback(async (files: File[]) => {
    const validFiles = files.filter(
      (f) => f.name.endsWith('.txt') || f.name.endsWith('.zip')
    );
    if (validFiles.length === 0) {
      setError('Please upload .txt or .zip hand history files');
      return;
    }
    const totalSize = validFiles.reduce((sum, f) => sum + f.size, 0);
    setFileInfo({ count: validFiles.length, size: totalSize });
    setUploading(true);
    setError(null);
    setResult(null);
    setProgress(null);
    try {
      const res = await uploadFilesStream(validFiles, (p) => setProgress(p));
      setResult(res);
      const h = await getHealth();
      setHandCount(h.hands);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed');
    } finally {
      setUploading(false);
      setProgress(null);
      setFileInfo(null);
    }
  }, []);

  const collectFilesFromEntry = useCallback(
    (entry: FileSystemEntry): Promise<File[]> => {
      return new Promise((resolve) => {
        if (entry.isFile) {
          (entry as FileSystemFileEntry).file((f) => resolve([f]));
        } else if (entry.isDirectory) {
          const reader = (entry as FileSystemDirectoryEntry).createReader();
          const allFiles: File[] = [];
          const readBatch = () => {
            reader.readEntries(async (entries) => {
              if (entries.length === 0) {
                resolve(allFiles);
                return;
              }
              for (const e of entries) {
                const files = await collectFilesFromEntry(e);
                allFiles.push(...files);
              }
              readBatch(); // continue reading (batched at 100 entries)
            });
          };
          readBatch();
        } else {
          resolve([]);
        }
      });
    },
    []
  );

  const onDrop = useCallback(
    async (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);

      const items = Array.from(e.dataTransfer.items);
      const entries = items
        .map((item) => item.webkitGetAsEntry?.())
        .filter(Boolean) as FileSystemEntry[];

      if (entries.length > 0) {
        const allFiles: File[] = [];
        for (const entry of entries) {
          const files = await collectFilesFromEntry(entry);
          allFiles.push(...files);
        }
        handleFiles(allFiles);
      } else {
        handleFiles(Array.from(e.dataTransfer.files));
      }
    },
    [handleFiles, collectFilesFromEntry]
  );

  const onFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files || []);
      handleFiles(files);
      e.target.value = '';
    },
    [handleFiles]
  );

  const saveName = async () => {
    if (!nameInput.trim()) return;
    const updated = await updateSettings({
      hero_username: nameInput.trim(),
      hero_site: settings?.hero_site || 'GG',
    });
    setSettings(updated);
    setEditingName(false);
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Import Hands</h1>
        <div className="flex items-center gap-3">
          <span className="text-sm text-text-muted">{handCount.toLocaleString()} hands in database</span>
          {handCount > 0 && (
            <>
              <button
                className="text-xs text-primary hover:text-primary-hover transition-colors disabled:opacity-50"
                disabled={uploading}
                onClick={async () => {
                  if (!confirm('Rebuild all stats from stored hands? This re-parses everything with the latest parser.')) return;
                  setUploading(true);
                  setError(null);
                  setResult(null);
                  setProgress(null);
                  try {
                    const res = await rebuildHands((p) => setProgress(p));
                    setResult(res);
                    const h = await getHealth();
                    setHandCount(h.hands);
                  } catch (e) {
                    setError(e instanceof Error ? e.message : 'Rebuild failed');
                  } finally {
                    setUploading(false);
                    setProgress(null);
                  }
                }}
              >
                Rebuild Stats
              </button>
              <button
                className="text-xs text-red hover:text-red/80 transition-colors"
                onClick={async () => {
                  if (!confirm('Clear all hands from the database? This cannot be undone.')) return;
                  await clearDatabase();
                  const h = await getHealth();
                  setHandCount(h.hands);
                  setResult(null);
                }}
              >
                Clear DB
              </button>
            </>
          )}
        </div>
      </div>

      {/* Hero username */}
      <div className="bg-surface rounded-lg border border-border p-4">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-sm text-text-muted">Hero: </span>
            {editingName ? (
              <span className="inline-flex gap-2 items-center">
                <input
                  className="bg-background border border-border rounded px-2 py-1 text-sm text-text"
                  value={nameInput}
                  onChange={(e) => setNameInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && saveName()}
                  autoFocus
                />
                <button
                  className="text-xs text-primary hover:text-primary-hover"
                  onClick={saveName}
                >
                  Save
                </button>
                <button
                  className="text-xs text-text-muted hover:text-text"
                  onClick={() => setEditingName(false)}
                >
                  Cancel
                </button>
              </span>
            ) : (
              <span>
                <span className="font-medium">{settings?.hero_username || '...'}</span>
                <button
                  className="ml-2 text-xs text-text-muted hover:text-primary"
                  onClick={() => {
                    setNameInput(settings?.hero_username || '');
                    setEditingName(true);
                  }}
                >
                  Edit
                </button>
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Drop zone */}
      <div
        className={`border-2 border-dashed rounded-lg p-12 text-center transition-colors cursor-pointer ${
          dragging
            ? 'border-primary bg-primary/10'
            : 'border-border hover:border-text-muted'
        }`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <input
          id="file-input"
          type="file"
          multiple
          accept=".txt,.zip"
          className="hidden"
          onChange={onFileInput}
        />
        <input
          id="folder-input"
          type="file"
          // @ts-expect-error webkitdirectory is not in the type defs
          webkitdirectory=""
          className="hidden"
          onChange={onFileInput}
        />
        {uploading ? (
          <div className="space-y-3">
            {progress?.type === 'start' || progress?.type === 'progress' ? (
              <>
                <p className="text-text-muted text-sm">
                  {fileInfo && !progress?.total_hands
                    ? `Uploading ${fileInfo.count} file${fileInfo.count !== 1 ? 's' : ''} (${(fileInfo.size / 1024).toFixed(0)} KB)...`
                    : `Processing ${progress?.total_hands?.toLocaleString() ?? '...'} hands from ${progress?.files ?? fileInfo?.count ?? '?'} file${(progress?.files ?? fileInfo?.count ?? 0) !== 1 ? 's' : ''}...`
                  }
                </p>
                {progress?.total != null && progress.total > 0 && (
                  <>
                    <div className="w-full bg-background rounded-full h-2 overflow-hidden">
                      <div
                        className="bg-primary h-2 rounded-full transition-all duration-200"
                        style={{ width: `${Math.round(((progress.processed ?? 0) / progress.total) * 100)}%` }}
                      />
                    </div>
                    <div className="flex justify-between text-xs text-text-muted">
                      <span>{(progress.processed ?? 0).toLocaleString()} / {progress.total.toLocaleString()}</span>
                      <span>{Math.round(((progress.processed ?? 0) / progress.total) * 100)}%</span>
                    </div>
                    <div className="flex gap-4 justify-center text-xs">
                      <span className="text-green">{(progress.imported ?? 0).toLocaleString()} imported</span>
                      <span className="text-yellow">{(progress.duplicates ?? 0).toLocaleString()} duplicates</span>
                      {(progress.errors ?? 0) > 0 && (
                        <span className="text-red">{(progress.errors ?? 0).toLocaleString()} errors</span>
                      )}
                      {(progress.hands_per_sec ?? 0) > 0 && (
                        <span className="text-text-muted">{progress.hands_per_sec?.toLocaleString()} h/s</span>
                      )}
                    </div>
                  </>
                )}
              </>
            ) : (
              <p className="text-text-muted">
                {fileInfo
                  ? `Uploading ${fileInfo.count} file${fileInfo.count !== 1 ? 's' : ''} (${(fileInfo.size / 1024).toFixed(0)} KB)...`
                  : 'Uploading...'}
              </p>
            )}
          </div>
        ) : (
          <>
            <p className="text-lg mb-2">Drop files or folders here</p>
            <p className="text-sm text-text-muted mb-4">.txt files, .zip archives, or folders</p>
            <div className="flex gap-3 justify-center">
              <button
                type="button"
                className="px-4 py-2 text-sm bg-primary text-white rounded hover:bg-primary-hover transition-colors"
                onClick={(e) => {
                  e.stopPropagation();
                  document.getElementById('file-input')?.click();
                }}
              >
                Browse Files
              </button>
              <button
                type="button"
                className="px-4 py-2 text-sm bg-surface border border-border text-text rounded hover:bg-background transition-colors"
                onClick={(e) => {
                  e.stopPropagation();
                  document.getElementById('folder-input')?.click();
                }}
              >
                Browse Folder
              </button>
            </div>
          </>
        )}
      </div>

      {/* Results */}
      {result && (
        <div className="bg-surface rounded-lg border border-border p-4 space-y-2">
          <h3 className="font-medium">Import Complete</h3>
          {result.elapsed_ms != null && result.imported > 0 && (
            <p className="text-sm text-text-muted">
              {result.imported.toLocaleString()} hands in {(result.elapsed_ms / 1000).toFixed(1)}s ({result.hands_per_sec?.toLocaleString()} h/s)
            </p>
          )}
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-2xl font-bold text-green">{result.imported}</div>
              <div className="text-xs text-text-muted">Imported</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-yellow">{result.duplicates}</div>
              <div className="text-xs text-text-muted">Duplicates</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-red">{result.errors}</div>
              <div className="text-xs text-text-muted">Errors</div>
            </div>
          </div>
          {result.parse_ms != null && result.imported > 0 && (
            <div className="text-xs text-text-muted text-center">
              parse {result.parse_ms}ms / stats {result.stats_ms}ms / db {result.db_ms}ms
            </div>
          )}
          {result.error_details.length > 0 && (
            <div className="mt-3 text-xs text-red space-y-1">
              {result.error_details.map((e, i) => (
                <div key={i}>{e}</div>
              ))}
            </div>
          )}
        </div>
      )}

      {error && (
        <div className="bg-red/10 border border-red/30 rounded-lg p-4 text-red text-sm">
          {error}
        </div>
      )}
    </div>
  );
}
