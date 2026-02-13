/** Recursively collect File objects from a FileSystemEntry (file or directory). */
export function collectFilesFromEntry(entry: FileSystemEntry): Promise<File[]> {
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
