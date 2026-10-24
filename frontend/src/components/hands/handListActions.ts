import { toast } from 'sonner';
import { exportHandsText, getHandDetail } from '@/lib/api';
import type { HandListParams } from '@/lib/api';
import { count } from '@/lib/format';
import { EXPORT_FILENAME, EXPORT_MAX_HANDS, handHistoryText } from '@/lib/hands/hand-plot';

/** Copy a hand's original hand-history text to the clipboard (toast either way). */
export async function copyHandHistory(handId: string, playerId?: number): Promise<void> {
  try {
    const text = handHistoryText(await getHandDetail(handId, playerId));
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

/** Download the whole filtered list as one .txt (the list's current filters, chain, sort), toasting a cap notice. */
export async function downloadHandsExport(params: HandListParams): Promise<void> {
  const pending = toast.loading('Exporting hands…');
  try {
    const { blob, truncated } = await exportHandsText(params);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = EXPORT_FILENAME;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10_000);
    toast.dismiss(pending);
    if (truncated) toast.warning(`Export limited to the first ${count(EXPORT_MAX_HANDS)} hands`);
    else toast.success('Hands exported');
  } catch (e) {
    toast.dismiss(pending);
    toast.error('Could not export hands', { description: e instanceof Error ? e.message : undefined });
  }
}
