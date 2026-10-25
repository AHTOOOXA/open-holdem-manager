import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { HEAVY_QUERY } from '@/lib/query-policy';
import { getHeroes, getPlayers, type PlayerSummary } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import { formatRelativeDate } from '@/lib/utils';
import { useWorkspace } from '@/contexts/WorkspaceContext';
import { Button } from '@/components/ui/button';
import { createDataGridColumns, DataGrid, statCell } from '@/components/ui/data-grid';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

export interface PickedPlayer {
  id: number;
  username: string;
  site: string;
}

interface PlayerDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelect: (player: PickedPlayer) => void;
}

interface Row extends PlayerSummary {
  site: string;
  hero: boolean;
}

const col = createDataGridColumns<Row>();
const columns = col.columns([
  col.accessor('username', {
    header: 'Name',
    size: 180,
    meta: { hideable: false },
    cell: (i) => (
      <span className="flex items-center gap-1.5">
        <span className="truncate">{i.getValue()}</span>
        {i.row.original.hero && <span className="rounded-control bg-overlay-selected px-1 text-primary">You</span>}
      </span>
    ),
  }),
  col.accessor('site', { header: 'Site', size: 90, enableSorting: false, meta: { className: 'text-muted-foreground' } }),
  col.accessor('hands', { header: 'Hands', size: 80, meta: { numeric: true }, cell: (i) => i.getValue().toLocaleString() }),
  col.accessor('vpip', { header: 'VPIP', size: 70, meta: { numeric: true }, cell: statCell<Row>((r) => r.hands) }),
  col.accessor('pfr', { header: 'PFR', size: 70, meta: { numeric: true }, cell: statCell<Row>((r) => r.hands) }),
  col.accessor('last_seen', {
    header: 'Last seen',
    size: 100,
    meta: { align: 'right', className: 'text-muted-foreground' },
    cell: (i) => (i.getValue() ? formatRelativeDate(i.getValue() as string) : ''),
  }),
]);

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

function SinglePicker({ onPick, onCancel }: { onPick: (p: PickedPlayer) => void; onCancel: () => void }) {
  const { activeWorkspaceId, activeWorkspace } = useWorkspace();
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<string[]>([]);
  const q = useDebounced(search.trim(), 250);

  const params = { search: q || undefined, sort_by: 'hands', sort_dir: 'desc', per_page: 100 };
  const players = useQuery({
    queryKey: queryKeys.players.list({ ...params, ws: activeWorkspaceId, picker: true }),
    queryFn: ({ signal }) => getPlayers(params, signal),
    placeholderData: (p) => p,
    ...HEAVY_QUERY,
  });
  const heroes = useQuery({ queryKey: ['heroes', activeWorkspaceId], queryFn: () => getHeroes(activeWorkspaceId), staleTime: 60_000 });

  const rows = useMemo<Row[]>(() => {
    const accounts = heroes.data?.accounts ?? [];
    const fallbackSite = heroes.data?.active?.site_name ?? activeWorkspace?.hero_site ?? '';
    const out = (players.data?.players ?? []).map((p) => {
      const acc = accounts.find((a) => a.username === p.username);
      return { ...p, site: p.site ?? acc?.site_name ?? fallbackSite, hero: !!acc };
    });
    return [...out.filter((r) => r.hero), ...out.filter((r) => !r.hero)];
  }, [players.data, heroes.data, activeWorkspace]);

  const current = rows.find((r) => String(r.id) === selected[0]);
  const pick = (r: Row | undefined) => {
    if (r) onPick({ id: r.id, username: r.username, site: r.site });
  };

  return (
    <div className="flex flex-col gap-3">
      <Input
        autoFocus
        type="search"
        aria-label="Search players"
        placeholder="Search players"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault();
            pick(current ?? rows[0]);
          }
        }}
      />
      <DataGrid
        ariaLabel="Players"
        columns={columns}
        data={rows}
        getRowId={(r) => String(r.id)}
        density="compact"
        rowLines
        selection="single"
        selectedRowIds={selected}
        onSelectionChange={setSelected}
        onRowActivate={pick}
        loading={players.isPending}
        error={players.isError ? 'Could not load players' : undefined}
        empty={<span className="text-sm text-muted-foreground">No players found</span>}
        maxHeight={340}
      />
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>Cancel</Button>
        <Button type="button" disabled={!current} onClick={() => pick(current)}>Select</Button>
      </DialogFooter>
    </div>
  );
}

export default function PlayerDialog({ open, onOpenChange, onSelect }: PlayerDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Player</DialogTitle>
          <DialogDescription className="sr-only">Choose the player the reports are about.</DialogDescription>
        </DialogHeader>
        <Tabs defaultValue="single">
          <TabsList variant="line">
            <TabsTrigger value="single">Single</TabsTrigger>
            <Tooltip>
              <TooltipTrigger asChild>
                <span tabIndex={0}>
                  <TabsTrigger value="multiple" disabled>Multiple players</TabsTrigger>
                </span>
              </TooltipTrigger>
              <TooltipContent>Later</TooltipContent>
            </Tooltip>
          </TabsList>
          <TabsContent value="single" className="pt-3">
            <SinglePicker
              onCancel={() => onOpenChange(false)}
              onPick={(p) => {
                onSelect(p);
                onOpenChange(false);
              }}
            />
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
