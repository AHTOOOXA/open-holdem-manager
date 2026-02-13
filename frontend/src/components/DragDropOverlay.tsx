import { useEffect, useRef, useState, useCallback } from 'react';
import { FolderUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useImport } from '@/contexts/ImportContext';
import { collectFilesFromEntry } from '@/lib/file-utils';

export default function DragDropOverlay() {
  const { startImport, phase, showImportOverlay, setShowImportOverlay } = useImport();
  const [dragging, setDragging] = useState(false);
  const counterRef = useRef(0);
  const fileRef = useRef<HTMLInputElement>(null);

  const visible = dragging || showImportOverlay;

  const handleFiles = useCallback(
    (files: File[]) => {
      counterRef.current = 0;
      setDragging(false);
      setShowImportOverlay(false);
      if (files.length > 0) startImport(files);
    },
    [startImport, setShowImportOverlay],
  );

  const onDrop = useCallback(
    async (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();

      if (phase !== 'idle') {
        counterRef.current = 0;
        setDragging(false);
        return;
      }

      const items = Array.from(e.dataTransfer?.items ?? []);
      const entries = items
        .map((item) => item.webkitGetAsEntry?.())
        .filter(Boolean) as FileSystemEntry[];

      let files: File[];
      if (entries.length > 0) {
        const all: File[] = [];
        for (const entry of entries) {
          all.push(...(await collectFilesFromEntry(entry)));
        }
        files = all;
      } else {
        files = Array.from(e.dataTransfer?.files ?? []);
      }

      handleFiles(files);
    },
    [handleFiles, phase],
  );

  useEffect(() => {
    const onDragEnter = (e: DragEvent) => {
      e.preventDefault();
      if (!e.dataTransfer?.types.includes('Files')) return;
      counterRef.current++;
      if (counterRef.current === 1 && phase === 'idle') {
        setDragging(true);
      }
    };

    const onDragLeave = (e: DragEvent) => {
      e.preventDefault();
      counterRef.current--;
      if (counterRef.current <= 0) {
        counterRef.current = 0;
        setDragging(false);
      }
    };

    const onDragOver = (e: DragEvent) => {
      e.preventDefault();
    };

    document.addEventListener('dragenter', onDragEnter);
    document.addEventListener('dragleave', onDragLeave);
    document.addEventListener('dragover', onDragOver);
    document.addEventListener('drop', onDrop);

    return () => {
      document.removeEventListener('dragenter', onDragEnter);
      document.removeEventListener('dragleave', onDragLeave);
      document.removeEventListener('dragover', onDragOver);
      document.removeEventListener('drop', onDrop);
    };
  }, [phase, onDrop]);

  // Close on Escape
  useEffect(() => {
    if (!showImportOverlay) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setShowImportOverlay(false);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [showImportOverlay, setShowImportOverlay]);

  if (!visible) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm"
      onClick={(e) => {
        // Close when clicking the backdrop (not the inner card)
        if (e.target === e.currentTarget && showImportOverlay) {
          setShowImportOverlay(false);
        }
      }}
    >
      <div className="flex flex-col items-center gap-4 rounded-xl border-2 border-dashed border-primary bg-primary/5 px-16 py-12">
        <FolderUp className="size-12 text-primary" />
        <p className="text-lg font-medium text-primary">
          {dragging ? 'Drop files to import' : 'Import Hand Histories'}
        </p>
        <p className="text-sm text-text-muted">
          {dragging ? '.txt or .zip hand histories' : 'Drop files here or browse'}
        </p>
        {!dragging && (
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={() => fileRef.current?.click()}
            >
              Browse Files
            </Button>
            <input
              ref={fileRef}
              type="file"
              multiple
              accept=".txt,.zip"
              className="hidden"
              onChange={(e) => {
                const files = Array.from(e.target.files || []);
                handleFiles(files);
                e.target.value = '';
              }}
            />
          </>
        )}
      </div>
    </div>
  );
}
