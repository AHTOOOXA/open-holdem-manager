import { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { getPlayers, getIdentities, createIdentity, addAlias } from '@/lib/api';
import type { PlayerListParams, Identity } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import { formatRelativeDate } from '@/lib/utils';
import PlayerTypeBadge from '@/components/PlayerTypeBadge';
import EmptyState from '@/components/EmptyState';
import Pagination from '@/components/hands/Pagination';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useWorkspace } from '@/contexts/WorkspaceContext';
import { Plus, UserPlus, Users } from 'lucide-react';

const PLAYER_TYPES = ['All', 'NIT', 'TAG', 'LAG', 'REC', 'MAN', 'UNK'] as const;
const WELL_KNOWN_TAGS = ['me', 'student', 'reg', 'fish', 'coach'] as const;

const TAG_COLORS: Record<string, string> = {
  me: 'bg-primary/20 text-primary border-primary/30',
  student: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  reg: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  fish: 'bg-green/20 text-green border-green/30',
  coach: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
};

function IdentityCard({ identity, onClick }: { identity: Identity; onClick: () => void }) {
  return (
    <div
      onClick={onClick}
      className="p-3 rounded-lg border border-border bg-surface hover:bg-surface-hover cursor-pointer transition-colors"
    >
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-2 min-w-0">
          {identity.color && (
            <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: identity.color }} />
          )}
          <span className="font-medium text-[14px] truncate">{identity.display_name}</span>
        </div>
        <span className="text-[12px] text-text-muted font-mono shrink-0">
          {identity.total_hands.toLocaleString()} hands
        </span>
      </div>
      {identity.tags.length > 0 && (
        <div className="flex gap-1 flex-wrap mb-1.5">
          {identity.tags.map((tag) => (
            <Badge key={tag} variant="outline" className={`text-[11px] px-1.5 py-0 h-5 ${TAG_COLORS[tag] || ''}`}>
              {tag}
            </Badge>
          ))}
        </div>
      )}
      {identity.aliases.length > 0 && (
        <div className="text-[12px] text-text-muted truncate">
          {identity.aliases.map((a) => a.username).join(', ')}
        </div>
      )}
      {identity.aliases.length === 0 && (
        <div className="text-[12px] text-text-muted italic">No linked players</div>
      )}
    </div>
  );
}

function LinkToIdentityDialog({
  open,
  onOpenChange,
  playerId,
  playerName,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  playerId: number;
  playerName: string;
}) {
  const qc = useQueryClient();
  const { activeWorkspaceId } = useWorkspace();
  const [newName, setNewName] = useState('');
  const [mode, setMode] = useState<'select' | 'create'>('select');

  const { data: identities } = useQuery({
    queryKey: queryKeys.identities.list,
    queryFn: getIdentities,
    enabled: open,
  });

  const linkMut = useMutation({
    mutationFn: (identityId: number) => addAlias(identityId, { workspace_id: activeWorkspaceId, player_id: playerId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.identities.list });
      onOpenChange(false);
    },
  });

  const createAndLinkMut = useMutation({
    mutationFn: async () => {
      const identity = await createIdentity({ display_name: newName || playerName });
      return addAlias(identity.id, { workspace_id: activeWorkspaceId, player_id: playerId });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.identities.list });
      onOpenChange(false);
      setNewName('');
      setMode('select');
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Link "{playerName}" to Identity</DialogTitle>
        </DialogHeader>

        {mode === 'select' ? (
          <div className="space-y-3">
            {identities && identities.length > 0 ? (
              <div className="space-y-1.5 max-h-60 overflow-y-auto">
                {identities.map((id) => (
                  <button
                    key={id.id}
                    onClick={() => linkMut.mutate(id.id)}
                    disabled={linkMut.isPending}
                    className="w-full text-left p-2 rounded hover:bg-surface-hover transition-colors flex items-center justify-between"
                  >
                    <span className="text-[14px]">{id.display_name}</span>
                    <span className="text-[12px] text-text-muted">{id.aliases.length} aliases</span>
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-[13px] text-text-muted text-center py-4">No identities yet</p>
            )}
            {linkMut.isError && (
              <p className="text-red text-[12px]">Failed to link. Player may already be linked.</p>
            )}
            <div className="border-t border-border pt-3">
              <Button variant="outline" size="sm" className="w-full" onClick={() => setMode('create')}>
                <Plus className="w-3.5 h-3.5 mr-1.5" />
                Create New Identity
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <Input
              placeholder={playerName}
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="h-8 text-[13px]"
            />
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => setMode('select')}>Back</Button>
              <Button
                size="sm"
                onClick={() => createAndLinkMut.mutate()}
                disabled={createAndLinkMut.isPending}
              >
                Create & Link
              </Button>
            </div>
            {createAndLinkMut.isError && (
              <p className="text-red text-[12px]">Failed to create identity.</p>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default function PlayersPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(50);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('All');
  const [minHands, setMinHands] = useState(20);
  const [sortBy, setSortBy] = useState('hands');
  const [sortDir, setSortDir] = useState('desc');
  const [tagFilter, setTagFilter] = useState<string | null>(null);
  const [linkDialog, setLinkDialog] = useState<{ playerId: number; playerName: string } | null>(null);

  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (searchTimeout.current) clearTimeout(searchTimeout.current);
    searchTimeout.current = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => { if (searchTimeout.current) clearTimeout(searchTimeout.current); };
  }, [search]);

  // ── Identities ────────────────────────────────────────────────────
  const { data: identities } = useQuery({
    queryKey: queryKeys.identities.list,
    queryFn: getIdentities,
  });

  const filteredIdentities = identities?.filter((id) => {
    if (!tagFilter) return true;
    return id.tags.includes(tagFilter);
  });

  // ── Opponents ─────────────────────────────────────────────────────
  const queryParams: PlayerListParams = {
    page,
    per_page: perPage,
    search: debouncedSearch || undefined,
    player_type: typeFilter !== 'All' ? typeFilter : undefined,
    min_hands: minHands,
    sort_by: sortBy,
    sort_dir: sortDir,
  };

  const { data, isPending, isError } = useQuery({
    queryKey: queryKeys.players.list(queryParams),
    queryFn: () => getPlayers(queryParams),
  });

  const handleSort = (col: string) => {
    if (sortBy === col) {
      setSortDir(sortDir === 'desc' ? 'asc' : 'desc');
    } else {
      setSortBy(col);
      setSortDir('desc');
    }
    setPage(1);
  };

  const sortArrow = (col: string) => {
    if (sortBy !== col) return '';
    return sortDir === 'desc' ? ' \u2193' : ' \u2191';
  };

  // Set of player IDs already linked to an identity (in any workspace)
  const linkedPlayerIds = new Set(
    identities?.flatMap((id) => id.aliases.map((a) => a.player_id)) ?? [],
  );

  const hasFilters = debouncedSearch !== '' || typeFilter !== 'All' || minHands !== 20;

  return (
    <div className="space-y-6">
      {/* ── Section 1: Player Identities ────────────────────── */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Users className="w-4 h-4 text-text-muted" />
            <h2 className="text-[15px] font-semibold">Player Identities</h2>
            {identities && (
              <span className="text-[12px] text-text-muted">({identities.length})</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {/* Tag filters */}
            <div className="flex gap-1">
              {WELL_KNOWN_TAGS.map((tag) => (
                <button
                  key={tag}
                  onClick={() => setTagFilter(tagFilter === tag ? null : tag)}
                  className={`text-[11px] px-2 py-0.5 rounded-full border transition-colors ${
                    tagFilter === tag
                      ? TAG_COLORS[tag] || 'bg-surface-hover border-border'
                      : 'border-border text-text-muted hover:text-text hover:border-text-muted'
                  }`}
                >
                  {tag}
                </button>
              ))}
            </div>
          </div>
        </div>

        {filteredIdentities && filteredIdentities.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2">
            {filteredIdentities.map((id) => (
              <IdentityCard
                key={id.id}
                identity={id}
                onClick={() => navigate(`/players/identity/${id.id}`)}
              />
            ))}
          </div>
        ) : identities && identities.length === 0 ? (
          <div className="text-center py-6 text-[13px] text-text-muted border border-dashed border-border rounded-lg">
            No identities yet. Link a player below to create one.
          </div>
        ) : tagFilter ? (
          <div className="text-center py-4 text-[13px] text-text-muted">
            No identities with tag "{tagFilter}"
          </div>
        ) : null}
      </section>

      {/* ── Section 2: Opponent List ────────────────────────── */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <h2 className="text-[15px] font-semibold">Opponents</h2>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-3 mb-3 flex-wrap">
          <Input
            placeholder="Search players..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-56 h-8 text-[13px]"
          />
          <Select value={typeFilter} onValueChange={(v) => { setTypeFilter(v); setPage(1); }}>
            <SelectTrigger className="w-28 h-8 text-[13px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PLAYER_TYPES.map((t) => (
                <SelectItem key={t} value={t}>{t === 'All' ? 'All Types' : t}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="flex items-center gap-1.5">
            <span className="text-[12px] text-text-muted">Min hands:</span>
            <Input
              type="number"
              min={0}
              value={minHands}
              onChange={(e) => { setMinHands(Number(e.target.value) || 0); setPage(1); }}
              className="w-20 h-8 text-[13px]"
            />
          </div>
          {data && (
            <span className="text-[13px] text-text-muted ml-auto">
              {data.total.toLocaleString()} players
            </span>
          )}
        </div>

        {/* Table */}
        {isPending && !data ? (
          <p className="text-text-muted text-sm py-8 text-center">Loading players...</p>
        ) : isError ? (
          <p className="text-red text-sm py-8 text-center">Failed to load players</p>
        ) : !data || data.total === 0 ? (
          <EmptyState
            variant={hasFilters ? 'no-match' : 'no-data'}
            onClearFilters={hasFilters ? () => { setSearch(''); setTypeFilter('All'); setMinHands(20); setPage(1); } : undefined}
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="text-[13px] uppercase tracking-wide">
                    <TableHead className="py-2 px-2 h-auto cursor-pointer hover:text-text select-none" onClick={() => handleSort('username')}>
                      Player{sortArrow('username')}
                    </TableHead>
                    <TableHead className="py-2 px-2 h-auto">Type</TableHead>
                    <TableHead className="py-2 px-2 h-auto text-right cursor-pointer hover:text-text select-none" onClick={() => handleSort('hands')}>
                      Hands{sortArrow('hands')}
                    </TableHead>
                    <TableHead className="py-2 px-2 h-auto text-right cursor-pointer hover:text-text select-none" onClick={() => handleSort('vpip')}>
                      VPIP{sortArrow('vpip')}
                    </TableHead>
                    <TableHead className="py-2 px-2 h-auto text-right cursor-pointer hover:text-text select-none" onClick={() => handleSort('pfr')}>
                      PFR{sortArrow('pfr')}
                    </TableHead>
                    <TableHead className="py-2 px-2 h-auto text-right cursor-pointer hover:text-text select-none" onClick={() => handleSort('three_bet')}>
                      3-Bet{sortArrow('three_bet')}
                    </TableHead>
                    <TableHead className="py-2 px-2 h-auto text-right cursor-pointer hover:text-text select-none" onClick={() => handleSort('af')}>
                      AF{sortArrow('af')}
                    </TableHead>
                    <TableHead className="py-2 px-2 h-auto text-right cursor-pointer hover:text-text select-none" onClick={() => handleSort('last_seen')}>
                      Last Seen{sortArrow('last_seen')}
                    </TableHead>
                    <TableHead className="py-2 px-2 h-auto w-8" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.players.map((p) => (
                    <TableRow
                      key={p.id}
                      className="transition-colors text-[14px] hover:bg-surface-hover"
                    >
                      <TableCell
                        className="py-1.5 px-2 font-medium cursor-pointer"
                        onClick={() => navigate(`/players/${p.id}`)}
                      >
                        {p.username}
                      </TableCell>
                      <TableCell className="py-1.5 px-2">
                        <PlayerTypeBadge type={p.player_type} />
                      </TableCell>
                      <TableCell className="py-1.5 px-2 text-right font-mono text-text-muted">
                        {p.hands.toLocaleString()}
                      </TableCell>
                      <TableCell className="py-1.5 px-2 text-right font-mono">
                        {p.vpip !== null ? p.vpip.toFixed(1) : '\u2014'}
                      </TableCell>
                      <TableCell className="py-1.5 px-2 text-right font-mono">
                        {p.pfr !== null ? p.pfr.toFixed(1) : '\u2014'}
                      </TableCell>
                      <TableCell className="py-1.5 px-2 text-right font-mono">
                        {p.three_bet !== null ? p.three_bet.toFixed(1) : '\u2014'}
                      </TableCell>
                      <TableCell className="py-1.5 px-2 text-right font-mono">
                        {p.af !== null ? p.af.toFixed(2) : '\u2014'}
                      </TableCell>
                      <TableCell className="py-1.5 px-2 text-right text-text-muted text-[13px]">
                        {p.last_seen ? formatRelativeDate(p.last_seen) : '\u2014'}
                      </TableCell>
                      <TableCell className="py-1.5 px-1">
                        {!linkedPlayerIds.has(p.id) && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setLinkDialog({ playerId: p.id, playerName: p.username });
                            }}
                            className="p-1 rounded hover:bg-primary/20 text-text-muted hover:text-primary transition-colors"
                            title="Link to identity"
                          >
                            <UserPlus className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            <Pagination
              page={data.page}
              totalPages={data.total_pages}
              perPage={perPage}
              onPageChange={setPage}
              onPerPageChange={(pp) => { setPerPage(pp); setPage(1); }}
            />
          </>
        )}
      </section>

      {/* Link dialog */}
      {linkDialog && (
        <LinkToIdentityDialog
          open
          onOpenChange={(open) => { if (!open) setLinkDialog(null); }}
          playerId={linkDialog.playerId}
          playerName={linkDialog.playerName}
        />
      )}
    </div>
  );
}
