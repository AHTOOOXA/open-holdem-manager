import { toast } from 'sonner';
import { currentHandsExportUrl } from '@/lib/api';
import type { HandListParams } from '@/lib/api';
import { queryClient } from '@/lib/query-client';
import { handDetailQuery } from '@/components/hands/handDetailQuery';
import { EXPORT_FILENAME, exportCapNotice, handHistoryText } from '@/lib/hands/hand-plot';

/** Copy a hand's original hand-history text to the clipboard (toast either way). Reuses the cached detail. */
export async function copyHandHistory(handId: string, playerId?: number): Promise<void> {
  try {
    const text = handHistoryText(await queryClient.fetchQuery(handDetailQuery(handId, playerId)));
    if (text === null) {
      toast.error('This hand has no stored hand history');
      return;
    }
    await navigator.clipboard.writeText(text);
    toast.success('Hand history copied');
  } catch (e) {
    toast.error('Could not copy the hand history', { description: e instanceof Error ? e.message : undefined });
  }
}

let exportBusy = false;

/**
 * Download the whole filtered list as one .txt (the list's current filters, chain, sort). The browser (Electron:
 * will-download) streams the server's attachment straight to disk, so nothing is buffered here. A second export
 * while one is starting is ignored; a list over the server cap warns first that only the first hands are exported.
 */
export async function downloadHandsExport(params: HandListParams, total?: number): Promise<void> {
  if (exportBusy) return;
  exportBusy = true;
  try {
    const notice = exportCapNotice(total);
    if (notice) toast.warning(notice);
    const a = document.createElement('a');
    a.href = currentHandsExportUrl(params);
    a.download = EXPORT_FILENAME;
    a.hidden = true;
    document.body.appendChild(a);
    a.click();
    a.remove();
    if (!notice) toast.success('Export started');
    // The download has no completion event: hold the guard for a moment so a double click is one export
    await new Promise((r) => setTimeout(r, 2000));
  } finally {
    exportBusy = false;
  }
}
