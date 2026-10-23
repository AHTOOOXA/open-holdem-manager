/**
 * Lower block of a Reports page: tab strip (Hands + split reports, overflow menu, "+" picker,
 * right-click or Delete to remove a tab) and the selected report.
 */
import { useRef, useState, type KeyboardEvent, type MouseEvent } from 'react';
import { Plus } from 'lucide-react';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { usePageLevel } from '@/components/page-chain/PageChain';
import HandExplorer, { type HandExplorerProps } from '@/components/hands/HandExplorer';
import SelectReportDialog from './SelectReportDialog';
import SplitReport from './SplitReport';
import { LOWER_TAB_CAPTION } from '@/lib/reports/catalog';
import { isLowerTab, type LowerTab, type ReportPageState } from '@/lib/reports/pages';
import type { ReportQuery, SplitRow, SplitType } from '@/lib/reports/types';
import { cn } from '@/lib/utils';

/** HandExplorer with the Reports `chain` prop (added by the hands track; harmless until then). */

const HANDS_GRID_MAX_HEIGHT = 'max(18rem, calc(100dvh - 22rem))';

export interface HandsInit {
  initialFilters?: HandExplorerProps['initialFilters'];
  fixedParams?: HandExplorerProps['fixedParams'];
  /** Remount key so new initial filters apply. */
  rev: number;
}

export default function LowerReports({ state, query, handsInit, onSelectTab, onAddTab, onRemoveTab, onOpenRow }: {
  state: ReportPageState;
  /** Full chain of the page. */
  query: ReportQuery;
  handsInit?: HandsInit;
  onSelectTab: (tab: LowerTab) => void;
  onAddTab: (type: SplitType) => void;
  onRemoveTab: (tab: LowerTab) => void;
  onOpenRow: (tab: SplitType, row: SplitRow) => void;
}) {
  const { lower } = usePageLevel();
  const [picker, setPicker] = useState(false);
  const [menu, setMenu] = useState<{ tab: LowerTab; x: number; y: number } | null>(null);
  const stripRef = useRef<HTMLDivElement>(null);

  const openMenu = (tab: LowerTab) => (e: MouseEvent<HTMLButtonElement>) => {
    if (tab === 'hands') return;
    e.preventDefault();
    // Keyboard-initiated context menus (Shift+F10, Menu key) report 0,0: anchor under the tab instead
    const r = e.currentTarget.getBoundingClientRect();
    const fromKeyboard = e.clientX === 0 && e.clientY === 0;
    setMenu({ tab, x: fromKeyboard ? r.left : e.clientX, y: fromKeyboard ? r.bottom : e.clientY });
  };
  const onTabKeyDown = (tab: LowerTab) => (e: KeyboardEvent<HTMLButtonElement>) => {
    if (tab !== 'hands' && (e.key === 'Delete' || e.key === 'Backspace')) {
      e.preventDefault();
      onRemoveTab(tab);
      requestAnimationFrame(() => stripRef.current?.querySelector<HTMLElement>('[role="tab"][data-state="active"]')?.focus());
    }
  };

  const tab = state.lowerTab;
  const selectedKey = (t: SplitType) => (state.selectedRow?.tab === t ? state.selectedRow.key : null);

  return (
    <div className={cn('flex min-h-150 flex-col gap-2 pt-2 pb-4', lower)}>
      <Tabs value={tab} onValueChange={(v) => { if (isLowerTab(v)) onSelectTab(v); }} className="gap-0">
        <div ref={stripRef} className="flex items-center gap-1 pr-3">
          <div className="min-w-0 flex-1">
            <TabsList variant="line" overflow aria-label="Reports" className="border-b-0 pl-3">
              {state.lowerTabs.map((t) => (
                <TabsTrigger
                  key={t}
                  value={t}
                  onContextMenu={openMenu(t)}
                  onKeyDown={onTabKeyDown(t)}
                  aria-description={t === 'hands' ? undefined : 'Right-click or press Delete to remove'}
                >
                  {LOWER_TAB_CAPTION[t]}
                </TabsTrigger>
              ))}
            </TabsList>
          </div>
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                aria-label="Add Report"
                onClick={() => setPicker(true)}
                className="inline-flex size-7 shrink-0 items-center justify-center rounded-control text-muted-foreground outline-none hover:bg-overlay-hover hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
              >
                <Plus className="size-4" aria-hidden />
              </button>
            </TooltipTrigger>
            <TooltipContent>Add Report</TooltipContent>
          </Tooltip>
        </div>
      </Tabs>

      <DropdownMenu open={menu !== null} onOpenChange={(o) => { if (!o) setMenu(null); }}>
        <DropdownMenuTrigger asChild>
          <span aria-hidden className="pointer-events-none fixed size-0" style={{ left: menu?.x ?? 0, top: menu?.y ?? 0 }} />
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="start"
          onCloseAutoFocus={(e) => {
            e.preventDefault();
            stripRef.current?.querySelector<HTMLElement>('[role="tab"][data-state="active"]')?.focus();
          }}
        >
          <DropdownMenuItem onSelect={() => { if (menu) onRemoveTab(menu.tab); }}>
            Remove {menu ? LOWER_TAB_CAPTION[menu.tab] : ''}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <div className="min-w-0 px-3">
        {tab === 'hands' ? (
          <HandExplorer
            key={handsInit?.rev ?? 0}
            chain={query.chain}
            initialFilters={handsInit?.initialFilters}
            fixedParams={query.player_id ? { ...handsInit?.fixedParams, player_id: query.player_id } : handsInit?.fixedParams}
            gridMaxHeight={HANDS_GRID_MAX_HEIGHT}
            emptyMessage="No results yet"
          />
        ) : (
          <SplitReport
            key={tab}
            type={tab}
            query={query}
            selectedKey={selectedKey(tab)}
            onOpenRow={(row) => onOpenRow(tab, row)}
          />
        )}
      </div>

      <SelectReportDialog
        open={picker}
        onOpenChange={setPicker}
        present={state.lowerTabs}
        onPick={onAddTab}
      />
    </div>
  );
}
