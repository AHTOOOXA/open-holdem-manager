import { useDayStartHour } from '@/hooks/useDayStart';
import { useMemo, useState } from 'react';
import { Pencil, Plus, Trash2 } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { getFilterOptions } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import { getQuickFilters } from '@/lib/reports/api';
import {
  POSITIONS,
  dateLabel,
  normaliseOwnSteps,
  presetDateStep,
  presetOf,
  sessionPresets,
  splitOwnSteps,
  stackLabel,
  tsizeName,
  type FilterTab,
} from '@/lib/reports/steps';
import type { Pos, QuickFilter, Step } from '@/lib/reports/types';
import { EMPTY_ROWS, LINE_MAX_LENGTH, rowsToDsl } from '@/lib/lines/dsl';
import { actionsLineStep, lineStepDescription, type LineStep } from '@/lib/lines/step';
import type { ActionRows } from '@/lib/lines/types';
import ActionsTab from './ActionsTab';
import LineBuilderDialog from './LineBuilderDialog';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { DatePicker } from '@/components/ui/date-picker';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

interface FilterDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The page's own steps; kinds this dialog does not edit pass through onApply unchanged. */
  value: Step[];
  onApply: (steps: Step[]) => void;
  initialTab?: FilterTab;
}

const GROUPS: { id: QuickFilter['group']; title: string }[] = [
  { id: 'preflop', title: 'Preflop' },
  { id: 'flop', title: 'Flop' },
  { id: 'turn', title: 'Turn' },
  { id: 'river', title: 'River' },
];
const TSIZES = [2, 6, 9];

interface Draft {
  row: { key: string; label: string } | null;
  pos: Pos[];
  stakes: string[];
  mode: 'fast' | 'regular' | '';
  tsize: number | null;
  lo: string;
  hi: string;
  presetId: string; // 'all' | preset id | 'custom'
  from: string;
  to: string;
  /** Actions tab rows (one `line` step carrying them). */
  rows: ActionRows;
  /** Custom Filter: the line builder's step. */
  custom: LineStep | null;
}

const EMPTY: Draft = {
  row: null, pos: [], stakes: [], mode: '', tsize: null, lo: '', hi: '', presetId: 'all', from: '', to: '', rows: EMPTY_ROWS, custom: null,
};

function toDraft(value: Step[]): Draft {
  const p = splitOwnSteps(value);
  const d: Draft = { ...EMPTY };
  if (p.row) d.row = { key: p.row.key, label: p.row.label ?? p.row.key };
  if (p.actions?.rows) d.rows = p.actions.rows;
  if (p.custom) d.custom = p.custom;
  if (p.pos) d.pos = [...p.pos.v];
  if (p.stakes) d.stakes = [...p.stakes.v];
  if (p.mode) d.mode = p.mode.v;
  if (p.tsize) d.tsize = p.tsize.v[0] ?? null;
  if (p.stack) {
    d.lo = p.stack.lo > 0 ? String(p.stack.lo) : '';
    d.hi = p.stack.hi != null ? String(p.stack.hi) : '';
  }
  if (p.date) {
    d.from = p.date.from ?? '';
    d.to = p.date.to ?? '';
    const stored = presetOf(p.date);
    d.presetId = stored && sessionPresets().some((x) => x.id === stored) ? stored : 'custom';
  }
  return d;
}

function num(s: string): number | null {
  const n = Number(s.trim());
  return s.trim() !== '' && Number.isFinite(n) && n >= 0 ? n : null;
}

/** Draft -> normalised own steps, with the steps the dialog does not edit passed through. */
function toSteps(d: Draft, value: Step[]): Step[] {
  const steps: Step[] = [];
  if (d.row) steps.push({ k: 'row', key: d.row.key, label: d.row.label });
  const actions = actionsLineStep(d.rows);
  if (actions) steps.push(actions);
  if (d.custom) steps.push(d.custom);
  if (d.pos.length) {
    const v = POSITIONS.filter((p) => d.pos.includes(p));
    steps.push({ k: 'pos', v, label: v.join(', ') });
  }
  if (d.stakes.length) steps.push({ k: 'stakes', v: d.stakes, label: d.stakes.join(', ') });
  if (d.mode) steps.push({ k: 'mode', v: d.mode, label: d.mode === 'fast' ? 'Fast Fold' : 'Regular' });
  if (d.tsize != null) steps.push({ k: 'tsize', v: [d.tsize], label: tsizeName(d.tsize) });
  let lo = num(d.lo);
  let hi = num(d.hi);
  if (lo != null && hi != null && lo > hi) [lo, hi] = [hi, lo];
  if (lo != null || hi != null) steps.push({ k: 'stack', lo: lo ?? 0, hi, label: stackLabel(lo ?? 0, hi) });
  if (d.from || d.to) {
    const preset = sessionPresets().find((x) => x.id === d.presetId);
    // Presets other than a custom range stay relative (re-derived from the preset id)
    steps.push(preset?.from
      ? presetDateStep(preset)
      : { k: 'date', from: d.from || undefined, to: d.to || undefined, label: dateLabel(d.from, d.to) });
  }
  return normaliseOwnSteps([...steps, ...splitOwnSteps(value).other]);
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <h3 className="text-xs font-medium text-muted-foreground">{title}</h3>
      {children}
    </div>
  );
}

function QuickTab({ draft, set }: { draft: Draft; set: (p: Partial<Draft>) => void }) {
  const { data, isPending, isError, refetch } = useQuery({ queryKey: ['reports', 'quick-filters'], queryFn: getQuickFilters, staleTime: Infinity });
  if (isPending) return <p className="py-6 text-center text-sm text-muted-foreground">Loading quick filters...</p>;
  if (isError)
    return (
      <div className="flex flex-col items-center gap-2 py-6 text-sm text-muted-foreground">
        <p>Could not load quick filters.</p>
        <Button variant="outline" size="sm" onClick={() => refetch()}>Retry</Button>
      </div>
    );
  return (
    <div role="radiogroup" aria-label="Quick filter" className="flex max-h-[50vh] flex-col gap-3 overflow-y-auto pr-1">
      {GROUPS.map((g) => {
        const items = data.filter((q) => q.group === g.id);
        if (!items.length) return null;
        return (
          <Section key={g.id} title={g.title}>
            <div className="flex flex-col">
              {items.map((q) => {
                const on = draft.row?.key === q.key;
                return (
                  <button
                    key={q.key}
                    type="button"
                    role="radio"
                    aria-checked={on}
                    onClick={() => set({ row: on ? null : { key: q.key, label: q.label } })}
                    className={cn(
                      'flex h-row-dense items-center gap-2 rounded-control px-2 text-left text-sm outline-none hover:bg-overlay-hover focus-visible:ring-2 focus-visible:ring-ring',
                      on && 'bg-selection',
                    )}
                  >
                    <span className={cn('size-3 shrink-0 rounded-full border border-border', on && 'border-primary bg-primary')} aria-hidden />
                    {q.label}
                  </button>
                );
              })}
            </div>
          </Section>
        );
      })}
    </div>
  );
}

function PositionsTab({ draft, set }: { draft: Draft; set: (p: Partial<Draft>) => void }) {
  return (
    <Section title="Hero position (none = any)">
      <ToggleGroup
        type="multiple"
        variant="outline"
        aria-label="Hero position"
        value={draft.pos}
        onValueChange={(v) => set({ pos: v as Pos[] })}
      >
        {POSITIONS.map((p) => (
          <ToggleGroupItem key={p} value={p} aria-label={p}>{p}</ToggleGroupItem>
        ))}
      </ToggleGroup>
    </Section>
  );
}

function GeneralTab({ draft, set }: { draft: Draft; set: (p: Partial<Draft>) => void }) {
  const { data } = useQuery({ queryKey: queryKeys.filterOptions, queryFn: getFilterOptions, staleTime: 60_000 });
  const stakes = useMemo(() => [...new Set([...(data?.stakes ?? []), ...draft.stakes])], [data, draft.stakes]);
  const toggleStake = (s: string, on: boolean) =>
    set({ stakes: on ? [...draft.stakes, s] : draft.stakes.filter((x) => x !== s) });
  return (
    <div className="flex flex-col gap-4">
      <Section title="Stakes (none = any)">
        <div className="flex flex-wrap gap-x-4 gap-y-1.5">
          {stakes.length === 0 && <span className="text-sm text-subtle-foreground">No stakes yet</span>}
          {stakes.map((s) => (
            <label key={s} className="flex cursor-pointer items-center gap-1.5 text-sm">
              <Checkbox checked={draft.stakes.includes(s)} onCheckedChange={(c) => toggleStake(s, c === true)} />
              {s}
            </label>
          ))}
        </div>
      </Section>
      <Section title="Game mode">
        <ToggleGroup
          type="single"
          variant="outline"
          aria-label="Game mode"
          value={draft.mode || 'any'}
          onValueChange={(v) => v && set({ mode: v === 'any' ? '' : (v as 'fast' | 'regular') })}
        >
          <ToggleGroupItem value="any">Any</ToggleGroupItem>
          <ToggleGroupItem value="fast">Fast Fold</ToggleGroupItem>
          <ToggleGroupItem value="regular">Regular</ToggleGroupItem>
        </ToggleGroup>
      </Section>
      <Section title="Table size">
        <ToggleGroup
          type="single"
          variant="outline"
          aria-label="Table size"
          value={draft.tsize == null ? 'any' : String(draft.tsize)}
          onValueChange={(v) => v && set({ tsize: v === 'any' ? null : Number(v) })}
        >
          <ToggleGroupItem value="any">Any</ToggleGroupItem>
          {TSIZES.map((n) => (
            <ToggleGroupItem key={n} value={String(n)}>{tsizeName(n)}</ToggleGroupItem>
          ))}
        </ToggleGroup>
      </Section>
      <Section title="Hero starting stack (bb)">
        <div className="flex items-center gap-2">
          <Input type="number" min={0} inputMode="decimal" aria-label="Stack from, bb" placeholder="From" className="w-24" value={draft.lo} onChange={(e) => set({ lo: e.target.value })} />
          <span className="text-muted-foreground" aria-hidden>-</span>
          <Input type="number" min={0} inputMode="decimal" aria-label="Stack to, bb" placeholder="To" className="w-24" value={draft.hi} onChange={(e) => set({ hi: e.target.value })} />
          <span className="text-sm text-muted-foreground">bb</span>
        </div>
      </Section>
    </div>
  );
}

function SessionTab({ draft, set }: { draft: Draft; set: (p: Partial<Draft>) => void }) {
  const dayHour = useDayStartHour();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const presets = useMemo(() => sessionPresets(), [dayHour]);
  return (
    <div className="flex flex-col gap-4">
      <Section title="Period">
        <div role="radiogroup" aria-label="Date preset" className="grid grid-cols-3 gap-1.5">
          {presets.map((p) => {
            const on = draft.presetId === p.id;
            return (
              <Button
                key={p.id}
                type="button"
                role="radio"
                aria-checked={on}
                variant={on ? 'secondary' : 'outline'}
                size="sm"
                onClick={() => set({ presetId: p.id, from: p.from ?? '', to: p.to ?? '' })}
              >
                {p.label}
              </Button>
            );
          })}
        </div>
      </Section>
      <Section title="Custom range">
        <div className="flex items-center gap-2">
          <DatePicker value={draft.from} placeholder="From" onChange={(v) => set({ from: v, presetId: v || draft.to ? 'custom' : 'all' })} />
          <span className="text-muted-foreground" aria-hidden>-</span>
          <DatePicker value={draft.to} placeholder="To" onChange={(v) => set({ to: v, presetId: v || draft.from ? 'custom' : 'all' })} />
        </div>
      </Section>
    </div>
  );
}

/** Footer left: "+ Custom Filter", or the set custom filter with edit / delete. */
function CustomFilterControl({ custom, onEdit, onDelete }: { custom: LineStep | null; onEdit: () => void; onDelete: () => void }) {
  if (!custom) {
    return (
      <button
        type="button"
        onClick={onEdit}
        className="inline-flex h-control items-center gap-1 rounded-pill border border-border pr-4 pl-3 text-xs text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Plus className="size-3.5" aria-hidden />
        Custom Filter
      </button>
    );
  }
  return (
    <div className="flex min-w-0 items-center gap-1">
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            onClick={onEdit}
            className="max-w-56 truncate rounded-control px-1 text-sm font-medium text-primary outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Custom Filter
          </button>
        </TooltipTrigger>
        <TooltipContent className="max-w-sm">{lineStepDescription(custom)}</TooltipContent>
      </Tooltip>
      <Button type="button" variant="ghost" size="icon-sm" aria-label="Edit custom filter" onClick={onEdit}>
        <Pencil aria-hidden />
      </Button>
      <Button type="button" variant="ghost" size="icon-sm" aria-label="Delete custom filter" onClick={onDelete}>
        <Trash2 aria-hidden />
      </Button>
    </div>
  );
}

function FilterForm({ value, onApply, onCancel, initialTab }: Omit<FilterDialogProps, 'open' | 'onOpenChange'> & { onCancel: () => void }) {
  const [draft, setDraft] = useState<Draft>(() => toDraft(value));
  const [tab, setTab] = useState<FilterTab>(initialTab ?? 'quick');
  const [builderOpen, setBuilderOpen] = useState(false);
  const set = (p: Partial<Draft>) => setDraft((d) => ({ ...d, ...p }));
  const actionsDsl = rowsToDsl(draft.rows);
  const marks = {
    quick: draft.row != null,
    positions: draft.pos.length > 0,
    general: draft.stakes.length > 0 || draft.mode !== '' || draft.tsize != null || num(draft.lo) != null || num(draft.hi) != null,
    actions: actionsDsl !== '',
    session: !!(draft.from || draft.to),
  };
  return (
    <>
      <Tabs value={tab} onValueChange={(v) => setTab(v as FilterTab)}>
        <TabsList variant="line">
          <TabsTrigger value="quick" marker={marks.quick}>Quick Filters</TabsTrigger>
          <TabsTrigger value="positions" marker={marks.positions}>Positions</TabsTrigger>
          <TabsTrigger value="general" marker={marks.general}>General</TabsTrigger>
          <TabsTrigger value="actions" marker={marks.actions}>Actions</TabsTrigger>
          <TabsTrigger value="session" marker={marks.session}>Session</TabsTrigger>
        </TabsList>
        <div className="min-h-56 pt-3">
          <TabsContent value="quick"><QuickTab draft={draft} set={set} /></TabsContent>
          <TabsContent value="positions"><PositionsTab draft={draft} set={set} /></TabsContent>
          <TabsContent value="general"><GeneralTab draft={draft} set={set} /></TabsContent>
          <TabsContent value="actions"><ActionsTab rows={draft.rows} onChange={(rows) => set({ rows })} /></TabsContent>
          <TabsContent value="session"><SessionTab draft={draft} set={set} /></TabsContent>
        </div>
      </Tabs>
      <DialogFooter className="sm:justify-between">
        <CustomFilterControl custom={draft.custom} onEdit={() => setBuilderOpen(true)} onDelete={() => set({ custom: null })} />
        <div className="flex gap-2">
          <Button type="button" variant="ghost" onClick={() => setDraft(EMPTY)}>Reset</Button>
          <Button type="button" variant="outline" onClick={onCancel}>Cancel</Button>
          <Button type="button" disabled={actionsDsl.length > LINE_MAX_LENGTH} onClick={() => onApply(toSteps(draft, value))}>Apply</Button>
        </div>
      </DialogFooter>
      <LineBuilderDialog
        open={builderOpen}
        onOpenChange={setBuilderOpen}
        initial={draft.custom}
        onOk={(custom) => set({ custom })}
      />
    </>
  );
}

export default function FilterDialog({ open, onOpenChange, value, onApply, initialTab }: FilterDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Filter</DialogTitle>
          <DialogDescription className="sr-only">Choose the filters for this report page.</DialogDescription>
        </DialogHeader>
        <FilterForm
          value={value}
          initialTab={initialTab}
          onCancel={() => onOpenChange(false)}
          onApply={(steps) => {
            onApply(steps);
            onOpenChange(false);
          }}
        />
      </DialogContent>
    </Dialog>
  );
}
