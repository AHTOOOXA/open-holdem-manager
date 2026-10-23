// STUB: replaced by the Stats tab track at merge. No real logic here.
import type { ReportQuery, Step } from '@/lib/reports/types';

export default function StatsTab({ query, onOpenStat }: { query: ReportQuery; onOpenStat: (step: Step, title: string) => void }) {
  void query;
  void onOpenStat;
  return <p className="py-8 text-center text-sm text-muted-foreground">Stats (placeholder)</p>;
}
