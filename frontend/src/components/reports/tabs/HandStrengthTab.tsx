// STUB: replaced by the Hand Strength tab track at merge. No real logic here.
import type { ReportQuery } from '@/lib/reports/types';

export default function HandStrengthTab({ query, selected, onSelect }: {
  query: ReportQuery;
  selected: { street: 'flop' | 'turn' | 'river'; cats: string[] } | null;
  onSelect: (v: { street: 'flop' | 'turn' | 'river'; cats: string[] } | null) => void;
}) {
  void query;
  void onSelect;
  return (
    <p className="py-8 text-center text-sm text-muted-foreground">
      Hand Strength (placeholder){selected ? `: ${selected.street} ${selected.cats.join(', ')}` : ''}
    </p>
  );
}
