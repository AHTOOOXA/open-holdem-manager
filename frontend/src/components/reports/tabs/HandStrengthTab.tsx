import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getHandStrength, queryKeyOf } from '@/lib/reports/api';
import type { ReportQuery, Street } from '@/lib/reports/types';
import { hvColor } from '@/lib/hv-color';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { barWidthPct, count, formatSignedBb, moneyClass, pct } from '@/lib/format';
import { cn } from '@/lib/utils';

type PostflopStreet = Exclude<Street, 'preflop'>;

export interface HandStrengthSelection {
  street: PostflopStreet;
  cats: string[];
}

interface HandStrengthTabProps {
  query: ReportQuery;
  selected: HandStrengthSelection | null;
  /** Called with the new selection; `cats` is empty when the last category is deselected. */
  onSelect: (sel: HandStrengthSelection) => void;
}

const STREETS: PostflopStreet[] = ['flop', 'turn', 'river'];
const COLUMNS = 'minmax(8rem, 12rem) minmax(6rem, 1fr) 4rem 3.5rem 4.5rem';

/** Hand Strength upper tab: hand-value categories on a street; multi-select categories to filter the next page. */
export default function HandStrengthTab({ query, selected, onSelect }: HandStrengthTabProps) {
  const [street, setStreet] = useState<PostflopStreet>(selected?.street ?? 'flop');
  const { data, isPending, isError, error } = useQuery({
    queryKey: ['reports', 'hand-strength', queryKeyOf(query), street],
    queryFn: ({ signal }) => getHandStrength({ ...query, street }, signal),
  });

  const selectedCats = selected && selected.street === street ? selected.cats : [];
  const toggle = (key: string) => {
    const cats = selectedCats.includes(key) ? selectedCats.filter((c) => c !== key) : [...selectedCats, key];
    onSelect({ street, cats });
  };
  const max = data?.rows.reduce((m, r) => Math.max(m, r.hands), 0) ?? 0;

  return (
    <div className="flex flex-col gap-2 p-3">
      <div className="flex items-center gap-3">
        <ToggleGroup type="single" value={street} onValueChange={(v) => v && setStreet(v as PostflopStreet)} aria-label="Street">
          {STREETS.map((s) => (
            <ToggleGroupItem key={s} value={s} className="h-control px-3 text-xs capitalize">
              {s}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        {data && <span className="text-xs text-muted-foreground">{count(data.known)} hands</span>}
        {selectedCats.length > 0 && (
          <Button variant="ghost" size="sm" className="ml-auto" onClick={() => onSelect({ street, cats: [] })}>
            Clear ({selectedCats.length})
          </Button>
        )}
      </div>
      {isPending ? (
        <div className="flex flex-col gap-1" aria-busy>
          {Array.from({ length: 10 }, (_, i) => (
            <Skeleton key={i} className="h-row-dense w-full" />
          ))}
        </div>
      ) : isError ? (
        <p role="alert" className="text-sm text-money-neg">
          Failed to load hand strength{error instanceof Error ? `: ${error.message}` : ''}
        </p>
      ) : data.rows.length === 0 || data.known === 0 ? (
        <p className="text-sm text-muted-foreground">No hands reach the {street} in this page.</p>
      ) : (
        <div role="listbox" aria-multiselectable aria-label="Hand strength categories">
          <div
            className="grid h-row-header items-center gap-2 px-2 text-label text-muted-foreground"
            style={{ gridTemplateColumns: COLUMNS }}
          >
            <span>Hand value</span>
            <span />
            <span className="text-right">Hands</span>
            <span className="text-right">%</span>
            <span className="text-right">Won bb</span>
          </div>
          {data.rows.map((r) => {
            const on = selectedCats.includes(r.key);
            // A selected row stays clickable even when it has no hands now, so it can be deselected
            const empty = r.hands === 0 && !on;
            return (
              <button
                key={r.key}
                type="button"
                role="option"
                aria-selected={on}
                disabled={empty}
                onClick={() => toggle(r.key)}
                onKeyDown={(e) => {
                  if (e.key === ' ') {
                    e.preventDefault();
                    toggle(r.key);
                  }
                }}
                className={cn(
                  'grid h-row-dense w-full items-center gap-2 rounded-control px-2 text-left text-cell outline-none',
                  empty ? 'cursor-default opacity-40' : 'cursor-pointer focus-visible:ring-2 focus-visible:ring-primary',
                  on ? 'bg-selection' : !empty && 'hover:bg-overlay-hover',
                )}
                style={{ gridTemplateColumns: COLUMNS }}
              >
                <span className="flex min-w-0 items-center gap-1.5">
                  <span className="truncate text-foreground">{r.label}</span>
                  {r.weak && (
                    <span className="shrink-0 rounded-pill border border-border px-1.5 text-2xs text-muted-foreground">weak</span>
                  )}
                </span>
                <span className="flex items-center" aria-hidden>
                  <span
                    className="block h-1.5 rounded-cell"
                    style={{ width: `${barWidthPct(r.hands, max)}%`, background: hvColor(r.key) }}
                  />
                </span>
                <span className="text-right tabular-nums text-foreground">{count(r.hands)}</span>
                <span className="text-right tabular-nums text-muted-foreground">{pct(r.pct, 0)}</span>
                <span className={cn('text-right tabular-nums', moneyClass(r.won_bb, 1))}>{formatSignedBb(r.won_bb)}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
