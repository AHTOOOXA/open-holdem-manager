import { useState } from 'react';
import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Info, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cellDetailQueryKey, getCellDetail } from '@/lib/api-general';
import type {
  CellDetail,
  GeneralFilterParams,
  HandsSelection,
  Ratio,
  SplitRow,
  StrengthBucket,
} from '@/lib/api-general';
import { H2N_THEME } from '@/lib/h2n-layout';
import type { GeneralCellMeta } from '@/lib/h2n-layout';
import { POPUP_THEME, formatRatio, popupTitle } from '@/lib/general-notation';
import { statAction, statTitle } from '@/lib/general-titles';
import BetSizesTab from './BetSizesTab';
import BoardsTab from './BoardsTab';
import type { SplitSelection } from './BoardsTab';
import GeneralHandList from './GeneralHandList';
import RangeTab from './RangeTab';
import StrengthBar from './StrengthBar';

type PopupTab = 'range' | 'boards' | 'bet_sizes' | 'hands';

const TAB_LABELS: Record<PopupTab, string> = {
  range: 'Range',
  boards: 'Boards',
  bet_sizes: 'Bet Sizes',
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
    <span className="inline-flex items-end gap-1" style={{ opacity: d.opacity }}>
      <span style={{ color: POPUP_THEME.value, fontSize: large ? 15 : 14 }}>{d.text}</span>
      {d.sampleText && (
        <span style={{ fontSize: H2N_THEME.sampleFontSize, color: H2N_THEME.sample, lineHeight: 'normal' }}>
          {d.sampleText}
        </span>
      )}
    </span>
  );
}

function SummaryItem({ r, label }: { r: Ratio; label: string }) {
  return (
    <div className="flex flex-col">
      <RatioValue r={r} />
      <span style={{ color: POPUP_THEME.label }}>{label}</span>
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
    <div className="flex items-stretch gap-4 text-sm" style={{ lineHeight: '18.67px' }}>
      <SummaryItem r={won_hand} label="Won Hand" />
      <SummaryItem r={wtsd} label="WTSD" />
      <SummaryItem r={wsd} label="W%SD" />
      {right.length > 0 && (
        <>
          <div aria-hidden className="w-px self-stretch" style={{ background: POPUP_THEME.divider }} />
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
  /** Current selection (drives the hands pane to the right). */
  selection: HandsSelection | null;
  onSelect: (selection: HandsSelection) => void;
  onClose: () => void;
}

/**
 * Page 1 of the General screen: the detail of one action stat
 * (docs/specs/H2N-COMPATIBLE-STATS.md section 6). Header with the stat name, the stat
 * value with its hand-value strength bar, Won Hand / WTSD / W%SD and hero's
 * next decision, then the Range / Boards / Bet Sizes / Hands tabs. Picking a
 * category, board or bet size opens its hands on page 2.
 */
export default function StatPopup({ cellId, meta, params, selection, onSelect, onClose }: StatPopupProps) {
  const isPreflop = meta.street === 'preflop';
  const tabs: PopupTab[] = isPreflop ? ['bet_sizes', 'hands'] : ['range', 'boards', 'bet_sizes', 'hands'];
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
    staleTime: 60_000,
  });

  const title = titleFor(meta);

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
      className="flex h-full w-[517px] shrink-0 flex-col border-l border-white/5"
      style={{ background: POPUP_THEME.bodyBg, fontFamily: H2N_THEME.fontFamily, fontSize: H2N_THEME.fontSize }}
    >
      {/* Header: title, stat value + bars, summary */}
      <div className="shrink-0 px-4 pt-3 pb-6" style={{ background: POPUP_THEME.headerBg }}>
        <div className="flex items-center justify-between gap-2">
          <span
            className="inline-flex min-w-0 items-center gap-2 rounded-full px-4 text-[15px] text-white"
            style={{ background: POPUP_THEME.titlePill, lineHeight: '33px' }}
          >
            <span className="truncate">{title}</span>
            <Tooltip>
              <TooltipTrigger asChild>
                <button type="button" className="shrink-0 cursor-help text-[#C3C3C3]" aria-label="About this stat">
                  <Info className="size-3.5" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="max-w-[360px]">
                <div className="space-y-1">
                  <div className="font-medium">{title}</div>
                  {data && (
                    <>
                      <div className="font-mono text-[11px] opacity-80">{data.notation}</div>
                      <div className="opacity-80">
                        {data.cases.toLocaleString()} of {data.opps.toLocaleString()} opportunities
                        {data.replay_failed > 0 ? ` · ${data.replay_failed} hands could not be replayed` : ''}
                      </div>
                    </>
                  )}
                </div>
              </TooltipContent>
            </Tooltip>
          </span>
          <Button
            variant="ghost"
            size="icon"
            className="size-8 shrink-0 text-[#A8A8A8] hover:text-white"
            onClick={onClose}
            aria-label="Close stat detail"
          >
            <X className="size-5" />
          </Button>
        </div>

        <div className="mt-5 grid items-center gap-y-[10px]" style={{ gridTemplateColumns: '72px 32px auto' }}>
          <span style={{ color: POPUP_THEME.label }}>Stat Value</span>
          <span>{data ? <RatioValue r={data} large /> : <span className="text-white/30">…</span>}</span>
          {!isPreflop ? (
            <StrengthBar strength={data?.strength} selectedKey={plainBucket} onSelect={selectBucket} />
          ) : (
            <span />
          )}
          <span style={{ color: POPUP_THEME.label }}>Vs-User</span>
          <span className="text-[#595959]">--</span>
          {!isPreflop ? <StrengthBar strength={null} /> : <span />}
        </div>

        <div className="mt-5 min-h-[37px]">{data && <SummaryRow detail={data} />}</div>
      </div>

      {/* Tabs */}
      <Tabs value={tab} onValueChange={changeTab} className="min-h-0 flex-1 gap-0">
        <TabsList variant="line" className="h-auto shrink-0 gap-8 px-4 pt-3 pb-2">
          {tabs.map((t) => (
            <TabsTrigger
              key={t}
              value={t}
              className="flex-none rounded-none px-0 text-[15px] font-semibold text-[#737373] after:bg-white data-[state=active]:text-white dark:text-[#737373] dark:data-[state=active]:text-white"
            >
              {TAB_LABELS[t]}
            </TabsTrigger>
          ))}
        </TabsList>

        {isPending ? (
          <p className="px-4 py-4 text-sm text-white/50">Loading…</p>
        ) : isError || !data ? (
          <p className="px-4 py-4 text-sm text-white/50">{(error as Error)?.message ?? 'Could not load the stat.'}</p>
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
            <TabsContent value="bet_sizes" className="min-h-0 overflow-y-auto">
              <BetSizesTab
                rows={data.bet_sizes}
                showRange={!isPreflop}
                selection={sizeSel}
                onSelectRow={selectSize}
                onSelectSegment={selectSizeSegment}
              />
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
