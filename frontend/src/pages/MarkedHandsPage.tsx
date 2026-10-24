import { useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { Settings, Tag } from 'lucide-react';
import { toast } from 'sonner';
import HandExplorer from '@/components/hands/HandExplorer';
import TagCheckboxGrid from '@/components/marked/TagCheckboxGrid';
import TagChip from '@/components/marked/TagChip';
import { useTagDefs } from '@/components/marked/useMarkHand';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { useWorkspace } from '@/contexts/WorkspaceContext';
import { exportMarkedUrl, importMarked, unmarkAll } from '@/lib/marked/api';
import { countLabel, getPageTagFilter, parseTagParam, pruneTagIds, setPageTagFilter, toggleId } from '@/lib/marked/logic';

export default function MarkedHandsPage() {
  const { activeWorkspaceId: ws } = useWorkspace();
  const qc = useQueryClient();
  const defs = useTagDefs();
  const [params, setParams] = useSearchParams();
  const urlTags = params.get('tag');

  // Per-workspace selection, kept in memory only; `?tag=` preselects (and replaces) it.
  const [byWs, setByWs] = useState<{ ws: number; ids: number[] }>(() => ({
    ws,
    ids: urlTags ? parseTagParam(urlTags) : getPageTagFilter(ws),
  }));
  const [seenUrl, setSeenUrl] = useState(urlTags);
  let current = byWs;
  if (current.ws !== ws) {
    current = { ws, ids: getPageTagFilter(ws) };
    setByWs(current);
  }
  if (seenUrl !== urlTags) {
    setSeenUrl(urlTags);
    if (urlTags) {
      current = { ws, ids: parseTagParam(urlTags) };
      setByWs(current);
      setPageTagFilter(ws, current.ids);
    }
  }
  const tagIds = useMemo(() => (defs.length > 0 ? pruneTagIds(current.ids, defs) : current.ids), [current.ids, defs]);
  const setTagIds = (ids: number[]) => {
    setByWs({ ws, ids });
    setPageTagFilter(ws, ids);
    if (params.has('tag')) {
      const next = new URLSearchParams(params);
      next.delete('tag');
      setParams(next, { replace: true });
    }
  };

  const fixedParams = useMemo(() => ({ marked: true, ...(tagIds.length > 0 ? { tag_ids: tagIds } : {}) }), [tagIds]);
  const selectedDefs = defs.filter((d) => tagIds.includes(d.id));

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['hands'] });
    qc.invalidateQueries({ queryKey: ['general', 'hands'] });
  };

  const fileRef = useRef<HTMLInputElement>(null);
  const onFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const t = toast.loading('Importing marked hands…');
    try {
      const r = await importMarked(ws, Array.from(files));
      toast.success(`Marked ${countLabel(r.marked, 'hand')}`, {
        id: t,
        description: `${r.imported} new, ${r.duplicates} already in the database${r.errors ? `, ${r.errors} with errors` : ''}.`,
      });
      refresh();
    } catch (e) {
      toast.error('Import failed', { id: t, description: e instanceof Error ? e.message : undefined });
    } finally {
      if (fileRef.current) fileRef.current.value = '';
    }
  };
  const download = (format: 'json' | 'txt') => {
    const a = document.createElement('a');
    a.href = exportMarkedUrl(ws, format, tagIds);
    a.download = '';
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const doUnmarkAll = async () => {
    setBusy(true);
    try {
      const r = await unmarkAll(ws, tagIds);
      toast.success(`Unmarked ${countLabel(r.unmarked, 'hand')}`);
      setConfirmOpen(false);
      refresh();
    } catch (e) {
      toast.error('Could not unmark hands', { description: e instanceof Error ? e.message : undefined });
    } finally {
      setBusy(false);
    }
  };
  const scope = tagIds.length > 0 ? 'with the selected tags' : 'in this workspace';

  return (
    <div className="mx-auto w-full max-w-[1600px] px-2">
      <HandExplorer
        fixedParams={fixedParams}
        hideFilters
        emptyMessage="No marked hands yet. Right-click a hand in any hand list and choose Mark Hand, or open it and use Mark."
        header={
          <div className="mb-2 flex items-center gap-2">
            <h1 className="text-xl font-bold text-foreground">Marked Hands</h1>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon-sm" aria-label="Marked hands actions">
                  <Settings />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start">
                <DropdownMenuItem onSelect={() => fileRef.current?.click()}>Import Marked Hands…</DropdownMenuItem>
                <DropdownMenuItem onSelect={() => download('json')}>Export Marked Hands…</DropdownMenuItem>
                <DropdownMenuItem onSelect={() => download('txt')}>Export as Plain Text…</DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem variant="destructive" onSelect={() => setConfirmOpen(true)}>Unmark All Hands</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <input
              ref={fileRef}
              type="file"
              multiple
              accept=".json,.txt,.zip"
              className="hidden"
              aria-label="Marked hands files"
              onChange={(e) => void onFiles(e.target.files)}
            />
          </div>
        }
        filterRow={
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="outline" size="sm" className="h-control gap-1.5 px-2">
                  <Tag className="size-3.5" /> Tags…
                </Button>
              </PopoverTrigger>
              <PopoverContent align="start" className="w-auto min-w-52 p-3">
                {defs.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No tags yet. Add some in Configuration.</p>
                ) : (
                  <TagCheckboxGrid tags={defs} selected={tagIds} onToggle={(id, on) => setTagIds(toggleId(tagIds, id, on))} />
                )}
              </PopoverContent>
            </Popover>
            {selectedDefs.map((d) => (
              <TagChip key={d.id} size="md" tag={d} onRemove={() => setTagIds(toggleId(tagIds, d.id, false))} />
            ))}
            {selectedDefs.length === 0 && <span className="text-xs text-muted-foreground">All marked hands</span>}
          </div>
        }
      />
      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Unmark all hands?</DialogTitle>
            <DialogDescription>
              Every marked hand {scope} loses its mark and its tags. The hands themselves stay in the database. This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmOpen(false)}>Cancel</Button>
            <Button variant="destructive" disabled={busy} onClick={() => void doUnmarkAll()}>Unmark</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
