import { useCallback, useRef, useState } from 'react';
import { useImport } from '@/contexts/ImportContext';
import { Button } from '@/components/ui/button';

function collectFilesFromEntry(entry: FileSystemEntry): Promise<File[]> {
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
          readBatch();
        });
      };
      readBatch();
    } else {
      resolve([]);
    }
  });
}

export default function ImportPopover({ onClose }: { onClose: () => void }) {
  const { startImport } = useImport();
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(
    (files: File[]) => {
      if (files.length === 0) return;
      startImport(files);
      onClose();
    },
    [startImport, onClose]
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
    [handleFiles]
  );

  const onFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files || []);
      handleFiles(files);
      e.target.value = '';
    },
    [handleFiles]
  );

  return (
    <div className="space-y-2">
      <div
        className={`border border-dashed rounded p-8 text-center transition-colors cursor-pointer ${
          dragging ? 'border-primary bg-primary/10' : 'border-border hover:border-text-muted'
        }`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => fileRef.current?.click()}
      >
        <p className="text-xs text-text-muted">Drop .txt/.zip files or folders</p>
      </div>
      <input
        ref={fileRef}
        type="file"
        multiple
        accept=".txt,.zip"
        className="hidden"
        onChange={onFileInput}
      />
      <Button size="sm" variant="outline" className="w-full" onClick={() => fileRef.current?.click()}>
        Browse Files
      </Button>
    </div>
  );
}
