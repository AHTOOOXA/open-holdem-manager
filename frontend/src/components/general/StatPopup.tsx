import { useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Info, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import SplitReport from '@/components/reports/SplitReport';
import PreflopRangeTab from '@/components/reports/tabs/PreflopRangeTab';
import { cellDetailQueryKey, getCellDetail } from '@/lib/api-general';
import type {
  CellDetail,
  GeneralFilterParams,
  HandsSelection,
  Ratio,
  SplitRow,
  StrengthBucket,
} from '@/lib/api-general';
import type { GeneralCellMeta } from '@/lib/h2n-layout';
import { grouped } from '@/lib/format';
import { formatRatio, popupTitle } from '@/lib/general-notation';
import type { ReportQuery, SplitRow as ReportSplitRow, Step } from '@/lib/reports/types';
import { cn } from '@/lib/utils';
import { statAction, statTitle } from '@/lib/general-titles';
import BetSizesTab from './BetSizesTab';
import BoardsTab from './BoardsTab';
import type { SplitSelection } from './BoardsTab';
import GeneralHandList from './GeneralHandList';
import RangeTab from './RangeTab';
import StrengthBar from './StrengthBar';

type PopupTab = 'range' | 'boards' | 'bet_sizes' | 'next_actions' | 'hands';

const TAB_LABELS: Record<PopupTab, string> = {
  range: 'Range',
  boards: 'Boards',
  bet_sizes: 'Bet Sizes',
  next_actions: 'Next Actions',
  hands: 'Hands',
};

/**
 * Last tab used, per (preflop / postflop, measured action type), kept for the
 * session like the reference (H2N-COMPATIBLE-STATS.md 6).
 */
const lastTab = new Map<string, PopupTab>();

/** The popup title is the stat's full descriptive name, arrows drawn. */
function titleFor(meta: GeneralCellMeta): string {
  return popupTitle(statTitle(meta));
}

function RatioValue({ r, large }: { r: Ratio | { cases: number; opps: number }; large?: boolean }) {
  const d = formatRatio(r);
  return (
    <span className="inline-flex items-end gap-1">
      <span className={cn(large ? 'text-base' : 'text-sm', d.opacity < 1 ? 'text-subtle-foreground' : 'text-foreground')}>
        {d.text}
      </span>
      {d.sampleText && <span className="text-2xs text-sample">{d.sampleText}</span>}
    </span>
  );
}

function SummaryItem({ r, label }: { r: Ratio; label: string }) {
  return (
    <div className="flex flex-col">
      <RatioValue r={r} />
      <span className="text-muted-foreground">{label}</span>
    </div>
  );
}

function SummaryRow({ detail }: { detail: CellDetail }) {
  const { won_hand, wtsd, wsd, next } = detail.summary;
  const right: ReactNode[] = [];
  if (next.show_fold_call_raise) {
    right.push(
      <SummaryItem key="f" r={next.fold} label="Fold" />,
      <SummaryItem key="c" r={next.call} label="Call" />,
      <SummaryItem key="r" r={next.raise} label="Raise" />,
    );
  }
  if (next.show_bet_check) {
    right.push(<SummaryItem key="b" r={next.bet} label="Bet" />, <SummaryItem key="x" r={next.check} label="Check" />);
  }
  return (
    <div className="flex items-stretch gap-4 text-sm leading-4.5">
      <SummaryItem r={won_hand} label="Won Hand" />
      <SummaryItem r={wtsd} label="WTSD" />
      <SummaryItem r={wsd} label="W%SD" />
      {right.length > 0 && (
        <>
          <div aria-hidden className="w-px self-stretch bg-border" />
          {right}
        </>
      )}
    </div>
  );
}

interface StatPopupProps {
  cellId: string;
  meta: GeneralCellMeta;
  params: GeneralFilterParams;
  /** Current Range category / board / bet size selection (drives the hands page to the right). */
  selection: HandsSelection | null;
  onSelect: (selection: HandsSelection) => void;
  /** Preflop Range tab (13x13): selected hand classes; a click hands the classes and the cell's chain over. */
  rangeCells?: string[];
  onSelectRange?: (cells: string[], chain: Step[]) => void;
  /** Next Actions tab: selected row key; a click hands the row and the cell's chain over. */
  nextKey?: string | null;
  onSelectNext?: (row: ReportSplitRow, chain: Step[]) => void;
  /** Absent = no close X (page 0 of a single-stat dashboard, or a page chain that has its own). */
  onClose?: () => void;
  /** Hide the title pill (the page chain header shows the title). */
  hideTitle?: boolean;
  /** Fill the parent (a page of a page chain) instead of the fixed-width pane. */
  embedded?: boolean;
}

/** The "(i)" button of the stat title: full name, matcher notation, cases of opportunities. */
export function StatInfo({ cellId, meta, params }: { cellId: string; meta: GeneralCellMeta; params: GeneralFilterParams }) {
  const { data } = useQuery({
    queryKey: cellDetailQueryKey(cellId, params),
    queryFn: () => getCellDetail(cellId, params),
    staleTime: Infinity, // like the grid: the data only changes on import / rebuild (invalidated there)
  });
  const title = titleFor(meta);
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          className="shrink-0 cursor-help rounded-pill text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-primary"
          aria-label="About this stat"
        >
          <Info className="size-3.5" />
        </button>
      </TooltipTrigger>
      <TooltipContent side="bottom" className="max-w-90">
        <div className="space-y-1">
          <div className="font-medium">{title}</div>
          {data && (
            <>
              <div className="font-mono text-label opacity-80">{data.notation}</div>
              <div className="opacity-80">
                {grouped(data.cases)} of {grouped(data.opps)} opportunities
                {data.replay_failed > 0 ? ` · ${data.replay_failed} hands could not be replayed` : ''}
              </div>
            </>
          )}
        </div>
      </TooltipContent>
    </Tooltip>
  );
}

function ChainMissing() {
  return <p className="px-4 py-4 text-sm text-muted-foreground">This report needs a newer backend.</p>;
}

/**
 * The detail of one action stat (docs/specs/H2N-COMPATIBLE-STATS.md section 6), a page of a
 * Statistics dashboard. Header with the stat name, the stat value with its hand-value strength
 * bar, Won Hand / WTSD / W%SD and hero's next decision, then the tabs: Range (postflop: hand-value
 * categories; preflop: the 13x13 grid), Boards (postflop), Bet Sizes, Next Actions and Hands.
 * Picking a category, board, bet size, grid class or Next Actions row opens its hands on the
 * next page; the 13x13 grid and Next Actions use the cell's Reports chain (`CellDetail.chain`).
 */
export default function StatPopup({
  cellId, meta, params, selection, onSelect, rangeCells, onSelectRange, nextKey, onSelectNext, onClose, hideTitle, embedded,
}: StatPopupProps) {
  const isPreflop = meta.street === 'preflop';
  const tabs: PopupTab[] = isPreflop
    ? ['range', 'bet_sizes', 'next_actions', 'hands']
    : ['range', 'boards', 'bet_sizes', 'next_actions', 'hands'];
  const memoryKey = `${isPreflop ? 'preflop' : 'postflop'}:${statAction(meta) ?? 'other'}`;
  const [tab, setTab] = useState<PopupTab>(() => {
    const t = lastTab.get(memoryKey);
    return t && tabs.includes(t) ? t : tabs[0];
  });
  const changeTab = (v: string) => {
    const t = v as PopupTab;
    lastTab.set(memoryKey, t);
    setTab(t);
  };

  const { data, isPending, isError, error } = useQuery({
    queryKey: cellDetailQueryKey(cellId, params),
    queryFn: () => getCellDetail(cellId, params),
    staleTime: Infinity, // like the grid: the data only changes on import / rebuild (invalidated there)
  });

  const title = titleFor(meta);

  // The Reports-backed tabs (13x13 Range, Next Actions) count exactly the cell's cases via its chain
  const detailChain = data?.chain;
  const workspaceId = params.workspace_id ?? 1;
  const playerId = params.player_id;
  const reportQuery = useMemo<ReportQuery | null>(() => {
    if (!detailChain) return null;
    const q: ReportQuery = { workspace_id: workspaceId, chain: detailChain };
    if (playerId != null) q.player_id = playerId;
    return q;
  }, [detailChain, workspaceId, playerId]);

  // Selection helpers: which part of the popup the current selection belongs to.
  const plainBucket = selection && !selection.board && !selection.size ? (selection.bucket ?? null) : null;
  const boardSel: SplitSelection | null = selection?.board
    ? { rowKey: selection.board, bucket: selection.bucket }
    : null;
  const sizeSel: SplitSelection | null = selection?.size ? { rowKey: selection.size, bucket: selection.bucket } : null;

  const selectBucket = (b: StrengthBucket) => onSelect({ label: b.label, bucket: b.key });
  const selectBoard = (row: SplitRow) => onSelect({ label: row.label, board: row.key });
  const selectBoardSegment = (row: SplitRow, b: StrengthBucket) =>
    onSelect({ label: `${row.label} · ${b.label}`, board: row.key, bucket: b.key });
  const selectSize = (row: SplitRow) => onSelect({ label: row.label, size: row.key });
  const selectSizeSegment = (row: SplitRow, b: StrengthBucket) =>
    onSelect({ label: `${row.label} · ${b.label}`, size: row.key, bucket: b.key });

  return (
    <section
      aria-label={`Stat detail: ${title}`}
      className={cn(
        'flex flex-col text-sm',
        embedded ? 'min-h-0 w-full flex-1' : 'h-full w-129 shrink-0 border-l border-border-subtle bg-surface-raised',
      )}
    >
      {/* Header: title, stat value + bars, summary */}
      <div className={cn('shrink-0 px-4 pt-3 pb-6', !embedded && 'bg-surface-sunken')}>
        {(!hideTitle || onClose) && (
          <div className="flex items-center justify-between gap-2">
            {!hideTitle ? (
              <span className="inline-flex h-6 min-w-0 items-center gap-1.5 rounded-pill bg-muted px-2 text-xs text-foreground">
                <span className="truncate">{title}</span>
                <StatInfo cellId={cellId} meta={meta} params={params} />
              </span>
            ) : <span />}
            {onClose && (
              <Button
                variant="ghost"
                size="icon"
                className="size-8 shrink-0 text-muted-foreground hover:text-foreground"
                onClick={onClose}
                aria-label="Close stat detail"
              >
                <X className="size-5" />
              </Button>
            )}
          </div>
        )}

        <div className={cn('grid items-center gap-y-2.5', (!hideTitle || onClose) && 'mt-5')} style={{ gridTemplateColumns: '72px 32px auto' }}>
          <span className="text-muted-foreground">Stat Value</span>
          <span>{data ? <RatioValue r={data} large /> : <span className="text-subtle-foreground">…</span>}</span>
          {!isPreflop ? (
            <StrengthBar strength={data?.strength} selectedKey={plainBucket} onSelect={selectBucket} />
          ) : (
            <span />
          )}
          <span className="text-muted-foreground">Vs-User</span>
          <span className="text-subtle-foreground">--</span>
          {!isPreflop ? <StrengthBar strength={null} /> : <span />}
        </div>

        <div className="mt-5 min-h-[37px]">{data && <SummaryRow detail={data} />}</div>
      </div>

      {/* Tabs */}
      <Tabs value={tab} onValueChange={changeTab} className="min-h-0 flex-1 gap-0">
        <TabsList variant="line" className="h-11 shrink-0 gap-8 px-4 pt-2">
          {tabs.map((t) => (
            <TabsTrigger
              key={t}
              value={t}
              className="flex-none rounded-none px-0 text-sm font-medium text-muted-foreground after:bg-primary hover:text-foreground data-[state=active]:text-foreground"
            >
              {TAB_LABELS[t]}
            </TabsTrigger>
          ))}
        </TabsList>

        {isPending ? (
          <p className="px-4 py-4 text-sm text-muted-foreground">Loading…</p>
        ) : isError || !data ? (
          <p className="px-4 py-4 text-sm text-muted-foreground">{(error as Error)?.message ?? 'Could not load the stat.'}</p>
        ) : (
          <>
            {!isPreflop && (
              <TabsContent value="range" className="min-h-0 overflow-y-auto">
                <RangeTab strength={data.strength} selectedKey={plainBucket} onSelect={selectBucket} />
              </TabsContent>
            )}
            {!isPreflop && (
              <TabsContent value="boards" className="min-h-0 overflow-y-auto">
                <BoardsTab
                  rows={data.boards}
                  selection={boardSel}
                  onSelectRow={selectBoard}
                  onSelectSegment={selectBoardSegment}
                />
              </TabsContent>
            )}
            {isPreflop && (
              <TabsContent value="range" className="min-h-0 overflow-y-auto px-4 py-3">
                {reportQuery && onSelectRange ? (
                  <PreflopRangeTab
                    query={reportQuery}
                    selected={rangeCells ?? []}
                    onSelect={(cells) => onSelectRange(cells, reportQuery.chain)}
                  />
                ) : <ChainMissing />}
              </TabsContent>
            )}
            <TabsContent value="bet_sizes" className="min-h-0 overflow-y-auto">
              <BetSizesTab
                rows={data.bet_sizes}
                showRange={!isPreflop}
                selection={sizeSel}
                onSelectRow={selectSize}
                onSelectSegment={selectSizeSegment}
              />
            </TabsContent>
            <TabsContent value="next_actions" className="min-h-0 overflow-y-auto px-2 py-2">
              {reportQuery && onSelectNext ? (
                <SplitReport
                  type="next_actions"
                  query={reportQuery}
                  selectedKey={nextKey ?? null}
                  onOpenRow={(row) => onSelectNext(row, reportQuery.chain)}
                />
              ) : <ChainMissing />}
            </TabsContent>
            <TabsContent value="hands" className="min-h-0">
              <GeneralHandList cellId={cellId} params={params} filter={{}} />
            </TabsContent>
          </>
        )}
      </Tabs>
    </section>
  );
}
