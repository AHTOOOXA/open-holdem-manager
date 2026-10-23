// STUB: replaced by the Preflop Range tab track at merge. No real logic here.
import type { ReportQuery } from '@/lib/reports/types';

export default function PreflopRangeTab({ query, selected, onSelect }: {
  query: ReportQuery;
  selected: string[];
  onSelect: (cells: string[]) => void;
}) {
  void query;
  void onSelect;
  return (
    <p className="py-8 text-center text-sm text-muted-foreground">
      Preflop Range (placeholder){selected.length > 0 ? `: ${selected.join(', ')}` : ''}
    </p>
  );
}
