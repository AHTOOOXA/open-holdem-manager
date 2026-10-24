/**
 * Line builder (Custom Filter): an ordered list of hero / villain actions per street, turned into
 * the matcher notation of a Reports `line` step (lib/lines). Opened from the filter dialog footer
 * ("+ Custom Filter") and by double-clicking a Custom Filter chip. Spec: reports/04 §2.10 (own
 * layout and look), docs/specs/QUERY-ENGINE-PRD.md "Action Line Builder".
 */
import { useId, useMemo, useState } from 'react';
import { ArrowLeft, ArrowRight, Trash2 } from 'lucide-react';
import {
  LINE_MAX_LENGTH, LINE_POSITIONS, LINE_STREETS, STREET_TITLE, actionChipLabel, describeLine, newActionId, raiseKindLabel,
  toDsl, validateLine,
} from '@/lib/lines/dsl';
import { customLineStep, lineOfStep, type LineStep } from '@/lib/lines/step';
import type { LineAction, LineActionType, LineActor, RaiseKind } from '@/lib/lines/types';
import type { Pos, Street } from '@/lib/reports/types';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Chip } from '@/components/ui/chip';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';

const TYPES: { a: LineActionType; verb: string }[] = [
  { a: 'raise', verb: 'Raises' },
  { a: 'call', verb: 'Calls' },
  { a: 'fold', verb: 'Folds' },
  { a: 'bet', verb: 'Bets' },
  { a: 'check', verb: 'Checks' },
];
const ACTORS: { who: LineActor; title: string }[] = [
  { who: 'hero', title: 'Hero' },
  { who: 'villain', title: 'Villain' },
];
const STREET_TEXT: Record<Street, string> = {
  preflop: 'text-foreground',
  flop: 'text-street-flop',
  turn: 'text-street-turn',
  river: 'text-street-river',
};

/** Order of the actions: by street, keeping the order inside a street. */
function byStreet(actions: LineAction[]): LineAction[] {
  return LINE_STREETS.flatMap((s) => actions.filter((a) => a.street === s));
}

/** Move action `id` to `street`, before `beforeId` (null = end of the lane). */
function moveTo(actions: LineAction[], id: string, street: Street, beforeId: string | null): LineAction[] {
  const moving = actions.find((a) => a.id === id);
  if (!moving || id === beforeId) return actions;
  const rest = actions.filter((a) => a.id !== id);
  const moved: LineAction = { ...moving, street };
  if (street === 'preflop' && moved.a === 'bet') moved.a = 'raise';
  const at = beforeId ? rest.findIndex((a) => a.id === beforeId) : -1;
  if (at >= 0) rest.splice(at, 0, moved);
  else {
    const lane = rest.filter((a) => a.street === street);
    const last = lane.length ? rest.indexOf(lane[lane.length - 1]) : -1;
    rest.splice(last >= 0 ? last + 1 : rest.length, 0, moved);
  }
  return byStreet(rest);
}

/** Swap with the neighbour on the same street (-1 left, +1 right). */
function shift(actions: LineAction[], id: string, dir: -1 | 1): LineAction[] {
  const a = actions.find((x) => x.id === id);
  if (!a) return actions;
  const lane = actions.filter((x) => x.street === a.street);
  const i = lane.indexOf(a);
  const j = i + dir;
  if (j < 0 || j >= lane.length) return actions;
  const swapped = [...lane];
  [swapped[i], swapped[j]] = [swapped[j], swapped[i]];
  return LINE_STREETS.flatMap((s) => (s === a.street ? swapped : actions.filter((x) => x.street === s)));
}

function Options({ action, index, laneSize, onChange, onMove, onRemove }: {
  action: LineAction;
  index: number;
  laneSize: number;
  onChange: (patch: Partial<LineAction>) => void;
  onMove: (dir: -1 | 1) => void;
  onRemove: () => void;
}) {
  const sameId = useId();
  const lastId = useId();
  const pre = action.street === 'preflop';
  const kinds: RaiseKind[] = pre ? ['any', 'open', '3bet'] : ['any', 'open'];
  return (
    <div className="flex flex-col gap-3 rounded-card border border-border-subtle bg-surface-sunken p-3" role="group" aria-label="Selected action">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium">
          {STREET_TITLE[action.street]}: {actionChipLabel(action)}
        </span>
        <div className="flex items-center gap-1">
          <Button type="button" variant="ghost" size="icon-sm" aria-label="Move left" disabled={index === 0} onClick={() => onMove(-1)}>
            <ArrowLeft aria-hidden />
          </Button>
          <Button type="button" variant="ghost" size="icon-sm" aria-label="Move right" disabled={index >= laneSize - 1} onClick={() => onMove(1)}>
            <ArrowRight aria-hidden />
          </Button>
          <Button type="button" variant="ghost" size="icon-sm" aria-label="Remove action" onClick={onRemove}>
            <Trash2 aria-hidden />
          </Button>
        </div>
      </div>
      <div className="grid grid-cols-[7rem_1fr] items-center gap-x-3 gap-y-2.5">
        <span className="text-xs text-muted-foreground">Action</span>
        <ToggleGroup
          type="single"
          variant="outline"
          size="sm"
          aria-label="Action type"
          value={action.a}
          onValueChange={(v) => v && onChange({ a: v as LineActionType })}
        >
          {TYPES.map((t) => (
            <ToggleGroupItem key={t.a} value={t.a} disabled={pre && t.a === 'bet'}>{t.verb}</ToggleGroupItem>
          ))}
        </ToggleGroup>
        {action.a === 'raise' && (
          <>
            <span className="text-xs text-muted-foreground">Raise</span>
            <ToggleGroup
              type="single"
              variant="outline"
              size="sm"
              aria-label="Raise kind"
              value={action.raise && kinds.includes(action.raise) ? action.raise : 'any'}
              onValueChange={(v) => v && onChange({ raise: v === 'any' ? undefined : (v as RaiseKind) })}
            >
              {kinds.map((k) => (
                <ToggleGroupItem key={k} value={k}>{k === 'any' ? 'Any' : raiseKindLabel(k, action.street)}</ToggleGroupItem>
              ))}
            </ToggleGroup>
          </>
        )}
        <span className="text-xs text-muted-foreground">Position</span>
        <div className="flex items-center gap-2">
          <ToggleGroup
            type="multiple"
            variant="outline"
            size="sm"
            aria-label={`${action.who === 'hero' ? 'Hero' : 'Villain'} position (none = any)`}
            value={action.pos ?? []}
            onValueChange={(v) => onChange({ pos: v.length ? (v as Pos[]) : undefined })}
          >
            {LINE_POSITIONS.map((p) => (
              <ToggleGroupItem key={p} value={p} disabled={pre && action.a === 'check' && p !== 'BB'}>{p}</ToggleGroupItem>
            ))}
          </ToggleGroup>
          <span className="text-xs text-subtle-foreground">{action.pos?.length ? '' : 'Any'}</span>
        </div>
        {action.who === 'villain' && (
          <>
            <label htmlFor={sameId} className="text-xs text-muted-foreground">Same villain</label>
            <div className="flex items-center gap-2">
              <Switch id={sameId} checked={action.same !== false} onCheckedChange={(c) => onChange({ same: c })} />
              <span className="text-xs text-subtle-foreground">
                {action.same !== false ? 'The one villain of this line' : 'Any other player'}
              </span>
            </div>
          </>
        )}
        <span aria-hidden />
        <label htmlFor={lastId} className="flex w-fit cursor-pointer items-center gap-2 text-sm">
          <Checkbox id={lastId} checked={action.last === true} onCheckedChange={(c) => onChange({ last: c === true || undefined })} />
          Last action of this player on this street
        </label>
      </div>
    </div>
  );
}

function BuilderForm({ initial, onCancel, onOk }: { initial: LineStep | null; onCancel: () => void; onOk: (step: LineStep) => void }) {
  const start = initial ? lineOfStep(initial) : null;
  const [name, setName] = useState(initial?.name ?? '');
  const [actions, setActions] = useState<LineAction[]>(() => byStreet(start?.actions ?? []));
  const [lane, setLane] = useState<Street>(() => start?.actions[0]?.street ?? 'preflop');
  const [selected, setSelected] = useState<string | null>(null);
  const [showDsl, setShowDsl] = useState(false);
  const [dragId, setDragId] = useState<string | null>(null);
  const nameId = useId();

  const check = useMemo(() => validateLine({ actions }), [actions]);
  const summary = describeLine(check.line);
  const dsl = toDsl(check.line);
  const errors = actions.length ? check.errors : [];
  const tooLong = dsl.length > LINE_MAX_LENGTH;
  const sel = actions.find((a) => a.id === selected) ?? null;
  const selLane = sel ? actions.filter((a) => a.street === sel.street) : [];

  const add = (who: LineActor, a: LineActionType) => {
    const act: LineAction = { id: newActionId(), street: lane, who, a };
    if (who === 'villain') act.same = true;
    if (lane === 'preflop' && a === 'check') act.pos = ['BB'];
    setActions((xs) => byStreet([...xs, act]));
    setSelected(act.id);
  };
  const patch = (id: string, p: Partial<LineAction>) =>
    setActions((xs) => xs.map((x) => {
      if (x.id !== id) return x;
      const next = { ...x, ...p };
      if (next.a !== 'raise') delete next.raise;
      if (next.street === 'preflop' && next.a === 'check') next.pos = ['BB'];
      return next;
    }));
  const remove = (id: string) => {
    setActions((xs) => xs.filter((x) => x.id !== id));
    setSelected((s) => (s === id ? null : s));
  };
  const select = (a: LineAction) => {
    setSelected(a.id);
    setLane(a.street);
  };
  const drop = (street: Street, beforeId: string | null) => (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (dragId) setActions((xs) => moveTo(xs, dragId, street, beforeId));
    setDragId(null);
    setLane(street);
  };

  return (
    <>
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-3">
          <label htmlFor={nameId} className="w-16 shrink-0 text-xs text-muted-foreground">Name</label>
          <Input id={nameId} value={name} onChange={(e) => setName(e.target.value)} placeholder={summary || 'Optional'} className="h-control" />
        </div>

        {initial && !start && (
          <p className="text-xs text-subtle-foreground">
            This line cannot be shown in the builder (notation: <code className="font-mono">{initial.dsl}</code>). OK replaces it.
          </p>
        )}

        <div className="flex flex-col gap-1.5" role="group" aria-label="Streets">
          {LINE_STREETS.map((street) => {
            const acts = actions.filter((a) => a.street === street);
            const current = lane === street;
            return (
              <div
                key={street}
                className={cn(
                  'flex min-h-10 items-center gap-2 rounded-control border px-2 py-1.5',
                  current ? 'border-primary bg-overlay-hover' : 'border-border-subtle',
                )}
                onDragOver={(e) => { if (dragId) e.preventDefault(); }}
                onDrop={drop(street, null)}
              >
                <button
                  type="button"
                  aria-pressed={current}
                  aria-label={`Add actions to ${STREET_TITLE[street]}`}
                  onClick={() => setLane(street)}
                  className={cn(
                    'w-16 shrink-0 self-stretch rounded-control text-left text-xs font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring',
                    STREET_TEXT[street],
                  )}
                >
                  {STREET_TITLE[street]}
                </button>
                <div className="flex min-w-0 flex-1 flex-wrap items-center gap-1.5">
                  {acts.length === 0 && <span className="text-xs text-subtle-foreground">{current ? 'Add actions below' : 'Any'}</span>}
                  {acts.map((a, i) => {
                    const label = actionChipLabel(a);
                    const on = a.id === selected;
                    return (
                      <Chip
                        key={a.id}
                        tone={a.who === 'hero' ? 'accent' : 'neutral'}
                        className={cn('cursor-grab', on && 'ring-2 ring-primary', dragId === a.id && 'opacity-60')}
                        draggable
                        onDragStart={(e) => { setDragId(a.id); e.dataTransfer.effectAllowed = 'move'; }}
                        onDragEnd={() => setDragId(null)}
                        onDragOver={(e) => { if (dragId) e.preventDefault(); }}
                        onDrop={drop(street, a.id)}
                        onKeyDown={(e) => {
                          if (!e.altKey) return;
                          if (e.key === 'ArrowLeft' && i > 0) { e.preventDefault(); setActions((xs) => shift(xs, a.id, -1)); }
                          if (e.key === 'ArrowRight' && i < acts.length - 1) { e.preventDefault(); setActions((xs) => shift(xs, a.id, 1)); }
                        }}
                        title="Alt + arrow keys or drag to reorder"
                        onClick={() => select(a)}
                        onRemove={() => remove(a.id)}
                        removeLabel={`Remove ${label}`}
                      >
                        {label}
                        {on && <span className="sr-only"> (selected)</span>}
                      </Chip>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>

        <div className="flex flex-col gap-1.5">
          <span className="text-xs text-muted-foreground">Add to {STREET_TITLE[lane]}</span>
          <div className="grid grid-cols-[4rem_repeat(5,minmax(0,1fr))] items-center gap-1.5">
            {ACTORS.map((who) => (
              <div key={who.who} className="contents">
                <span className="text-xs text-muted-foreground">{who.title}</span>
                {TYPES.map((t) => (
                  <Button
                    key={t.a}
                    type="button"
                    variant="outline"
                    size="sm"
                    aria-label={`${who.title} ${t.verb}`}
                    disabled={lane === 'preflop' && t.a === 'bet'}
                    onClick={() => add(who.who, t.a)}
                  >
                    {t.verb}
                  </Button>
                ))}
              </div>
            ))}
          </div>
        </div>

        {sel && (
          <Options
            key={sel.id}
            action={sel}
            index={selLane.indexOf(sel)}
            laneSize={selLane.length}
            onChange={(p) => patch(sel.id, p)}
            onMove={(dir) => setActions((xs) => shift(xs, sel.id, dir))}
            onRemove={() => remove(sel.id)}
          />
        )}

        {(errors.length > 0 || tooLong) && (
          <ul role="alert" className="flex flex-col gap-0.5 text-xs text-destructive">
            {errors.map((e) => <li key={e}>{e}</li>)}
            {tooLong && <li>The line is too long.</li>}
          </ul>
        )}
      </div>

      <div className="flex flex-col gap-1 border-t border-border-subtle pt-3">
        <p className="text-sm" aria-live="polite">
          {summary || <span className="text-subtle-foreground">No actions yet: pick a street, then add actions.</span>}
        </p>
        {dsl && (
          <div className="flex flex-col gap-1">
            <button
              type="button"
              aria-expanded={showDsl}
              onClick={() => setShowDsl((v) => !v)}
              className="w-fit rounded-control text-xs text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
            >
              {showDsl ? 'Hide notation' : 'Show notation'}
            </button>
            {showDsl && <code className="font-mono text-xs break-all text-muted-foreground">{dsl}</code>}
          </div>
        )}
      </div>

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>Cancel</Button>
        <Button
          type="button"
          disabled={!actions.length || errors.length > 0 || tooLong}
          onClick={() => {
            const step = customLineStep({ actions }, name);
            if (step) onOk(step);
          }}
        >
          OK
        </Button>
      </DialogFooter>
    </>
  );
}

export default function LineBuilderDialog({ open, onOpenChange, initial, onOk }: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The line step being edited; null = a new line. */
  initial: LineStep | null;
  onOk: (step: LineStep) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Custom Filter</DialogTitle>
          <DialogDescription>
            Actions on each street in order. Between two listed actions, other players may only fold or check.
          </DialogDescription>
        </DialogHeader>
        <BuilderForm
          initial={initial}
          onCancel={() => onOpenChange(false)}
          onOk={(step) => {
            onOk(step);
            onOpenChange(false);
          }}
        />
      </DialogContent>
    </Dialog>
  );
}
