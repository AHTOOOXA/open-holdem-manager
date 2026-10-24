import { Copy, FolderOpen } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { getSystemInfo, systemInfoQueryKey } from '@/lib/config/api';
import { getElectronAPI } from '@/lib/electron';
import { bytes } from '@/lib/format';

/** Read-only location and size of the database, with Open Folder (desktop app) or Copy path (browser). */
export default function DataFolderPanel() {
  const { data, isError } = useQuery({ queryKey: systemInfoQueryKey, queryFn: getSystemInfo, retry: false });
  const openFolder = getElectronAPI()?.openDataFolder;

  const copy = async () => {
    if (!data) return;
    try {
      await navigator.clipboard.writeText(data.data_dir);
      toast.success('Path copied');
    } catch {
      toast.error('Could not copy the path');
    }
  };
  const open = async () => {
    try {
      await openFolder?.();
    } catch (e) {
      toast.error('Could not open the folder', { description: e instanceof Error ? e.message : undefined });
    }
  };

  return (
    <section aria-labelledby="data-folder-title" className="rounded-card border border-border bg-card p-4">
      <h2 id="data-folder-title" className="text-sm font-semibold">Data Folder</h2>
      {isError && <p className="mt-2 text-sm text-muted-foreground">The location is not available.</p>}
      {data && (
        <div className="mt-2 flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate font-mono text-xs" title={data.data_dir}>{data.data_dir}</p>
            <p className="mt-1 text-xs text-muted-foreground">Database size {bytes(data.db_size_bytes)}</p>
          </div>
          {openFolder ? (
            <Button variant="outline" size="sm" className="shrink-0" onClick={() => void open()}>
              <FolderOpen className="size-3.5" />
              Open Folder
            </Button>
          ) : (
            <Button variant="outline" size="sm" className="shrink-0" onClick={() => void copy()}>
              <Copy className="size-3.5" />
              Copy path
            </Button>
          )}
        </div>
      )}
    </section>
  );
}
