import { useEffect, useMemo, useRef, useState } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { X } from 'lucide-react';
import HandDrawer, { type HandViewMode } from '@/components/hands/HandDrawer';
import HandHistoryDialog from '@/components/hands/HandHistoryDialog';
import HandRowMenuItems from '@/components/hands/HandRowMenuItems';
import TagPickerPopover from '@/components/marked/TagPickerPopover';
import { queryClient } from '@/lib/query-client';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  HANDS_MAX_ROWS,
  HANDS_PAGE_SIZE,
  cellHandsQueryKey,
  getCellHands,
} from '@/lib/api-general';
import type { GeneralFilterParams, HandsFilter, HandsOrder, HandsSort } from '@/lib/api-general';
import { formatRangeCount } from '@/lib/general-notation';
import type { HandStreet } from '@/lib/general-notation';
import GeneralHandRow from './GeneralHandRow';

const SORTS: { value: string; label: string; sort: HandsSort; order: HandsOrder }[] = [
  { value: 'date-desc', label: 'Newest first', sort: 'date', order: 'desc' },
  { value: 'date-asc', label: 'Oldest first', sort: 'date', order: 'asc' },
  { value: 'won-desc', label: 'Won: most', sort: 'won', order: 'desc' },
  { value: 'won-asc', label: 'Won: least', sort: 'won', order: 'asc' },
  { value: 'ev-desc', label: 'EV diff: most', sort: 'ev', order: 'desc' },
  { value: 'ev-asc', label: 'EV diff: least', sort: 'ev', order: 'asc' },
];

interface GeneralHandListProps {
  cellId: string;
  params: GeneralFilterParams;
  filter: HandsFilter;
  /** Title pill of the hands pane; omitted inside the popup's Hands tab. */
  title?: string;
  onClose?: () => void;
}

/**
 * The stat's hands (cases) for one popup selection, newest first, in H2N's
 * list notation. Loads 50 rows, then more as you scroll, up to 512 per sort
 * order. Click a row to select it, double-click (or Enter on its cards) to open the hand in the replayer drawer; right-click for the hand menu.
 */
export default function GeneralHandList({ cellId, params, filter, title, onClose }: GeneralHandListProps) {
  const [sortValue, setSortValue] = useState('date-desc');
  const { sort, order } = SORTS.find((s) => s.value === sortValue) ?? SORTS[0];
  const [expanded, setExpanded] = useState<ReadonlySet<HandStreet>>(new Set());
  const [openHandId, setOpenHandId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const playerId = params.player_id ?? undefined;
  const [drawerMode, setDrawerMode] = useState<HandViewMode>('visual');
  const [historyId, setHistoryId] = useState<string | null>(null);
  const [picker, setPicker] = useState<{ handId: string; playerId?: number; x: number; y: number } | null>(null);
  const lastPointer = useRef({ x: 0, y: 0 });
  // Keep focus where the dialog / picker puts it instead of handing it back to the row when the menu closes
  const overlayOpening = useRef(false);
  const openHand = (id: string, mode: HandViewMode = 'visual') => {
    setDrawerMode(mode);
    setSelectedId(id);
    setOpenHandId(id);
  };

  const query = useInfiniteQuery({
    queryKey: cellHandsQueryKey(cellId, params, filter, sort, order),
    queryFn: ({ pageParam }) =>
      getCellHands(cellId, params, {
        ...filter,
        sort,
        order,
        offset: pageParam,
        limit: Math.min(HANDS_PAGE_SIZE, HANDS_MAX_ROWS - pageParam),
      }),
    initialPageParam: 0,
    getNextPageParam: (last, pages) => {
      const loaded = pages.reduce((n, p) => n + p.rows.length, 0);
      const cap = Math.min(last.total, HANDS_MAX_ROWS);
      return last.rows.length > 0 && loaded < cap ? loaded : undefined;
    },
  });
  const { data, isPending, isError, error, hasNextPage, isFetchingNextPage, fetchNextPage } = query;

  const rows = useMemo(() => data?.pages.flatMap((p) => p.rows) ?? [], [data]);
  const total = data?.pages[0]?.total ?? 0;

  // Load the next page when the sentinel under the table scrolls into view.
  const scrollRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = sentinelRef.current;
    if (!el || !hasNextPage) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting) && !isFetchingNextPage) void fetchNextPage();
      },
      { root: scrollRef.current, rootMargin: '200px' },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage, rows.length]);

  const openIndex = openHandId ? rows.findIndex((r) => r.hand_id === openHandId) : -1;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex shrink-0 items-center gap-3 px-4 py-2">
        {title && (
          <span className="inline-flex h-6 items-center rounded-pill bg-muted px-2 text-xs whitespace-nowrap text-foreground">
            {title}
          </span>
        )}
        <span className="text-sm whitespace-nowrap text-muted-foreground">
          {data
            ? `${formatRangeCount(total)} hand${total === 1 ? '' : 's'}${total > HANDS_MAX_ROWS ? `, first ${HANDS_MAX_ROWS}` : ''}`
            : ''}
        </span>
        <div className="ml-auto flex items-center gap-1">
          <Select value={sortValue} onValueChange={setSortValue}>
            <SelectTrigger size="sm" className="h-7 w-[132px] border-border bg-transparent dark:bg-transparent text-xs text-muted-foreground" aria-label="Sort hands">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SORTS.map((s) => (
                <SelectItem key={s.value} value={s.value}>
                  {s.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {onClose && (
            <Button variant="ghost" size="icon" className="size-8 text-muted-foreground hover:text-foreground" onClick={onClose} aria-label="Close hands">
              <X />
            </Button>
          )}
        </div>
      </div>

      <div
        ref={scrollRef}
        className="min-h-0 flex-1 overflow-auto"
        onContextMenuCapture={(e) => { lastPointer.current = { x: e.clientX, y: e.clientY }; }}
      >
        {isPending ? (
          <p className="px-4 py-2 text-sm text-muted-foreground">Loading hands…</p>
        ) : isError ? (
          <p className="px-4 py-2 text-sm text-muted-foreground">{(error as Error)?.message ?? 'Could not load hands.'}</p>
        ) : rows.length === 0 ? (
          <p className="px-4 py-2 text-sm text-muted-foreground">No hands.</p>
        ) : (
          <>
            <table className="border-collapse text-sm leading-4.5">
              <tbody>
                {rows.map((r) => (
                  <GeneralHandRow
                    key={r.hand_id}
                    row={r}
                    expandedStreets={expanded}
                    onExpandStreet={(s) => setExpanded((prev) => new Set(prev).add(s))}
                    selected={r.hand_id === (openHandId ?? selectedId)}
                    onSelect={setSelectedId}
                    onOpen={(id) => openHand(id)}
                    onMenuCloseAutoFocus={(e) => {
                      if (overlayOpening.current) {
                        overlayOpening.current = false;
                        e.preventDefault();
                      }
                    }}
                    menu={
                      <HandRowMenuItems
                        handId={r.hand_id}
                        playerId={playerId}
                        marked={r.marked ?? (r.tags?.length ?? 0) > 0}
                        onOpenReplayer={() => openHand(r.hand_id)}
                        onShowDetails={() => openHand(r.hand_id, 'text')}
                        onPickTags={(id) => {
                          overlayOpening.current = true;
                          setPicker({ handId: id, playerId, ...lastPointer.current });
                        }}
                        onShowHistory={() => {
                          overlayOpening.current = true;
                          setHistoryId(r.hand_id);
                        }}
                      />
                    }
                  />
                ))}
              </tbody>
            </table>
            <div ref={sentinelRef} className="h-px" />
            {isFetchingNextPage && <p className="px-4 py-2 text-sm text-muted-foreground">Loading more…</p>}
          </>
        )}
      </div>

      {openHandId && (
        <HandDrawer
          handId={openHandId}
          playerId={playerId}
          initialMode={drawerMode}
          onClose={() => setOpenHandId(null)}
          onPrev={() => openIndex > 0 && setOpenHandId(rows[openIndex - 1].hand_id)}
          onNext={() => openIndex >= 0 && openIndex < rows.length - 1 && setOpenHandId(rows[openIndex + 1].hand_id)}
          onTagsChanged={() => { void queryClient.invalidateQueries({ queryKey: ['general', 'hands'] }); }}
        />
      )}
      {historyId && (
        <HandHistoryDialog
          handId={historyId}
          playerId={playerId}
          onClose={() => setHistoryId(null)}
          onCloseAutoFocus={(e) => {
            e.preventDefault();
            scrollRef.current?.querySelector<HTMLElement>(`tr[data-hand-id="${CSS.escape(historyId)}"] button`)?.focus();
          }}
        />
      )}
      {picker && (
        <TagPickerPopover
          key={picker.handId}
          handId={picker.handId}
          playerId={picker.playerId}
          initialTags={rows.find((r) => r.hand_id === picker.handId)?.tags ?? []}
          point={picker}
          onClose={() => setPicker(null)}
        />
      )}
    </div>
  );
}
