/**
 * Filter dialog, Actions tab: per-street "action rows" (hero's whole action on a street, e.g.
 * "Bet Call") and Faced Preflop. Rows on a street are OR'd, streets AND'd; the selection becomes
 * one `line` step (lib/lines `actionsLineStep`). Spec: reports/04 §2.5 (own layout).
 */
import { useId, useState } from 'react';
import {
  FACED_LABEL, LINE_MAX_LENGTH, LINE_STREETS, ROW_LABEL, STREET_TITLE, rowsToDsl, streetHasRows,
} from '@/lib/lines/dsl';
import type { ActionRows, FacedPreflop, StreetRow } from '@/lib/lines/types';
import type { Street } from '@/lib/reports/types';
import { Checkbox } from '@/components/ui/checkbox';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';

const PREFLOP_COLUMNS: StreetRow[][] = [
  ['raise', 'raise_fold', 'raise_call', 'raise_raise', 'fold'],
  ['call', 'call_fold', 'call_call', 'call_raise'],
];
const POSTFLOP_COLUMNS: StreetRow[][] = [
  ...PREFLOP_COLUMNS,
  ['bet', 'bet_fold', 'bet_call', 'bet_raise'],
  ['check', 'check_fold', 'check_call', 'check_raise'],
];
const FACED_COLUMNS: FacedPreflop[][] = [
  ['unopened', 'one_limp', 'two_plus_limps', 'limp_raise'],
  ['open_raise', 'open_3bet', 'raise_call', 'raise_calls'],
];

const ITEM_CLASS =
  'h-row-dense w-full justify-start rounded-control px-2 text-sm font-normal text-muted-foreground hover:bg-overlay-hover hover:text-foreground data-[state=on]:bg-selection data-[state=on]:font-medium data-[state=on]:text-primary';

/** One column of toggles; `value` / `onChange` work on the whole set, the column edits its share. */
function Column<T extends string>({ items, label, value, names, onChange }: {
  items: T[];
  label: string;
  value: readonly T[];
  names: Record<T, string>;
  onChange: (next: T[]) => void;
}) {
  return (
    <ToggleGroup
      type="multiple"
      orientation="vertical"
      spacing={1}
      aria-label={label}
      className="flex w-full flex-col items-stretch"
      value={items.filter((i) => value.includes(i))}
      onValueChange={(v) => onChange([...value.filter((x) => !items.includes(x)), ...(v as T[])])}
    >
      {items.map((i) => (
        <ToggleGroupItem key={i} value={i} className={ITEM_CLASS}>{names[i]}</ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h3 className="text-label font-medium tracking-wide text-muted-foreground uppercase">{children}</h3>;
}

function LastCheckbox({ street, rows, onChange }: { street: Street; rows: ActionRows; onChange: (r: ActionRows) => void }) {
  const id = useId();
  return (
    <label htmlFor={id} className="flex w-fit cursor-pointer items-center gap-2 text-sm">
      <Checkbox
        id={id}
        checked={rows.last[street] === true}
        onCheckedChange={(c) => onChange({ ...rows, last: { ...rows.last, [street]: c === true } })}
      />
      Selected action was the last action on this street
    </label>
  );
}

export default function ActionsTab({ rows, onChange }: { rows: ActionRows; onChange: (rows: ActionRows) => void }) {
  const [street, setStreet] = useState<Street>(() => LINE_STREETS.find((s) => streetHasRows(rows, s)) ?? 'preflop');
  const setRows = (s: Street, next: StreetRow[]) => onChange({ ...rows, streets: { ...rows.streets, [s]: next } });
  const faced = rows.faced ?? [];
  const preRows = rows.streets.preflop ?? [];
  const unopenedGap = faced.includes('unopened') && (preRows.length === 0 || preRows.includes('fold'));
  const tooLong = rowsToDsl(rows).length > LINE_MAX_LENGTH;

  return (
    <Tabs value={street} onValueChange={(v) => setStreet(v as Street)} className="gap-3">
      <TabsList aria-label="Street">
        {LINE_STREETS.map((s) => (
          <TabsTrigger key={s} value={s} marker={streetHasRows(rows, s)} className="px-3">{STREET_TITLE[s]}</TabsTrigger>
        ))}
      </TabsList>
      <TabsContent value="preflop" className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <SectionTitle>Faced preflop</SectionTitle>
          <div className="grid grid-cols-2 gap-x-4">
            {FACED_COLUMNS.map((items, i) => (
              <Column
                key={i}
                items={items}
                label={`Faced preflop, column ${i + 1}`}
                value={faced}
                names={FACED_LABEL}
                onChange={(next) => onChange({ ...rows, faced: next })}
              />
            ))}
          </div>
          {unopenedGap && (
            <p className="text-xs text-subtle-foreground">
              Unopened covers raises and calls: folds in an unopened pot cannot be filtered.
            </p>
          )}
        </div>
        <div className="flex flex-col gap-1.5">
          <SectionTitle>Preflop actions</SectionTitle>
          <div className="grid grid-cols-2 gap-x-4">
            {PREFLOP_COLUMNS.map((items, i) => (
              <Column
                key={i}
                items={items}
                label={`Preflop actions, column ${i + 1}`}
                value={preRows}
                names={ROW_LABEL}
                onChange={(next) => setRows('preflop', next)}
              />
            ))}
          </div>
        </div>
        <LastCheckbox street="preflop" rows={rows} onChange={onChange} />
      </TabsContent>
      {LINE_STREETS.filter((s) => s !== 'preflop').map((s) => (
        <TabsContent key={s} value={s} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <SectionTitle>{STREET_TITLE[s]} actions</SectionTitle>
            <div className="grid grid-cols-4 gap-x-3">
              {POSTFLOP_COLUMNS.map((items, i) => (
                <Column
                  key={i}
                  items={items}
                  label={`${STREET_TITLE[s]} actions, column ${i + 1}`}
                  value={rows.streets[s] ?? []}
                  names={ROW_LABEL}
                  onChange={(next) => setRows(s, next)}
                />
              ))}
            </div>
          </div>
          <LastCheckbox street={s} rows={rows} onChange={onChange} />
        </TabsContent>
      ))}
      {tooLong && (
        <p role="alert" className="text-xs text-destructive">
          Too many combinations of Faced Preflop and preflop actions: select fewer.
        </p>
      )}
    </Tabs>
  );
}
