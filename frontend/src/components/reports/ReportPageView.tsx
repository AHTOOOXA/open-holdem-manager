/**
 * Body of one Reports page: filter chips, upper tabs (Stats, Graph, Preflop Range, Hand Strength)
 * and the lower block. Upper tabs query [...inherited, ...own]; the lower block and the next page
 * use the full chain (plus the range / hand-strength selections).
 */
import { useDayKey } from '@/hooks/useDayStart';
import { useMemo, useState } from 'react';
import { Plus } from 'lucide-react';
import { Chip } from '@/components/ui/chip';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import FilterDialog from './FilterDialog';
import LineBuilderDialog from './LineBuilderDialog';
import { isCustomLineStep, lineStepDescription, type LineStep } from '@/lib/lines/step';
import LowerReports, { type HandsInit } from './LowerReports';
import StatsTab from './tabs/StatsTab';
import GraphTab from './tabs/GraphTab';
import PreflopRangeTab from './tabs/PreflopRangeTab';
import HandStrengthTab from './tabs/HandStrengthTab';
import {
  composeFull, composeUpper, filterTabFor, isUpperTab, reportQuery, selectedCells, selectedHv, stepLabel,
  type Dashboard, type FilterDialogTab, type HvSelection, type LowerTab, type ReportPage,
} from '@/lib/reports/pages';
import type { SplitRow, SplitType, Step } from '@/lib/reports/types';

export interface PageActions {
  setOwn: (steps: Step[]) => void;
  removeOwn: (stepIndex: number) => void;
  setCells: (cells: string[]) => void;
  setHv: (v: HvSelection | null) => void;
  setUpperTab: (tab: 'stats' | 'graph' | 'range' | 'strength') => void;
  setLowerTab: (tab: LowerTab) => void;
  addLowerTab: (type: SplitType) => void;
  removeLowerTab: (tab: LowerTab) => void;
  openRow: (tab: SplitType, row: SplitRow) => void;
  openStat: (step: Step, title: string) => void;
}

function FilterChips({ own, onAdd, onEdit, onRemove }: {
  own: Step[];
  onAdd: () => void;
  /** Double-click / Enter on chip `i`. */
  onEdit: (i: number) => void;
  onRemove: (i: number) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 px-6 pt-3" role="group" aria-label="Page filter">
      <button
        type="button"
        onClick={onAdd}
        className="inline-flex h-control items-center gap-1 rounded-pill border border-border pr-4 pl-3 text-xs text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Plus className="size-3.5" aria-hidden />
        Filter
      </button>
      {own.map((step, i) => {
        const label = stepLabel(step);
        return (
          <Chip
            // Steps have no ids; position + content is stable enough for a chip row
            key={`${i}:${label}`}
            tone="accent"
            // Custom Filter chips: the hover text is the line itself (the label may be a name)
            title={isCustomLineStep(step) ? `${lineStepDescription(step)}\nDouble-click to edit` : 'Double-click to edit'}
            onDoubleClick={() => onEdit(i)}
            // Mouse: double-click edits (Hand2Note). Keyboard (Enter/Space, detail 0): edit directly.
            onClick={(e) => { if (e.detail === 0) onEdit(i); }}
            onRemove={() => onRemove(i)}
            removeLabel={`Remove filter ${label}`}
          >
            {label}
          </Chip>
        );
      })}
    </div>
  );
}

export default function ReportPageView({ page, dashboard, actions, handsInit, onClearHandsInit }: {
  page: ReportPage;
  dashboard: Dashboard;
  actions: PageActions;
  handsInit?: HandsInit;
  onClearHandsInit?: () => void;
}) {
  const s = page.state;
  const [dialog, setDialog] = useState<{ open: boolean; tab: FilterDialogTab }>({ open: false, tab: 'quick' });
  // Custom Filter chip: the line builder opens directly and OK applies straight away (Hand2Note)
  const [builder, setBuilder] = useState<{ open: boolean; index: number }>({ open: false, index: -1 });
  const builderStep = builder.index >= 0 ? s.own[builder.index] : undefined;

  const dayKey = useDayKey();
  const { inherited } = page;
  const { own, lower } = s;
  const { workspaceId, playerId } = dashboard;
  const upperQuery = useMemo(
    () => reportQuery({ workspaceId, playerId }, composeUpper(inherited, own)),
    [workspaceId, playerId, inherited, own, dayKey], // eslint-disable-line react-hooks/exhaustive-deps
  );
  const lowerQuery = useMemo(
    () => reportQuery({ workspaceId, playerId }, composeFull(inherited, own, lower)),
    [workspaceId, playerId, inherited, own, lower, dayKey], // eslint-disable-line react-hooks/exhaustive-deps
  );
  const cells = useMemo(() => selectedCells(lower), [lower]);
  const hv = useMemo(() => selectedHv(lower), [lower]);

  return (
    <>
      <FilterChips
        own={own}
        onAdd={() => setDialog({ open: true, tab: 'quick' })}
        onEdit={(i) => {
          const step = own[i];
          if (step && isCustomLineStep(step)) setBuilder({ open: true, index: i });
          else if (step) setDialog({ open: true, tab: filterTabFor(step) });
        }}
        onRemove={actions.removeOwn}
      />
      <div className="flex flex-col gap-2 pt-2">
        <Tabs value={s.upperTab} onValueChange={(v) => { if (isUpperTab(v)) actions.setUpperTab(v); }} className="gap-0">
          <TabsList variant="line" aria-label="Report views" className="border-b-0 pl-3">
            <TabsTrigger value="stats">Stats</TabsTrigger>
            <TabsTrigger value="graph">Graph</TabsTrigger>
            <TabsTrigger value="range" marker={cells.length > 0}>Preflop Range</TabsTrigger>
            <TabsTrigger value="strength" marker={hv !== null}>Hand Strength</TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="min-w-0 px-6 py-4">
          {s.upperTab === 'stats' && <StatsTab query={upperQuery} onOpenStat={actions.openStat} />}
          {s.upperTab === 'graph' && <GraphTab query={upperQuery} />}
          {s.upperTab === 'range' && <PreflopRangeTab query={upperQuery} selected={cells} onSelect={actions.setCells} />}
          {s.upperTab === 'strength' && <HandStrengthTab query={upperQuery} selected={hv} onSelect={actions.setHv} />}
        </div>
        <LowerReports
          state={s}
          query={lowerQuery}
          handsInit={handsInit}
          onClearHandsInit={onClearHandsInit}
          onSelectTab={actions.setLowerTab}
          onAddTab={actions.addLowerTab}
          onRemoveTab={actions.removeLowerTab}
          onOpenRow={actions.openRow}
        />
      </div>
      <FilterDialog
        open={dialog.open}
        onOpenChange={(open) => setDialog((d) => ({ ...d, open }))}
        value={own}
        onApply={(steps) => { actions.setOwn(steps); setDialog((d) => ({ ...d, open: false })); }}
        initialTab={dialog.tab}
      />
      <LineBuilderDialog
        open={builder.open}
        onOpenChange={(open) => setBuilder((b) => ({ ...b, open }))}
        initial={builderStep && isCustomLineStep(builderStep) ? (builderStep as LineStep) : null}
        onOk={(step) => actions.setOwn(own.map((x, j) => (j === builder.index ? step : x)))}
      />
    </>
  );
}
