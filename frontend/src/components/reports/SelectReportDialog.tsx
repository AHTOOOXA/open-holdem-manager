/** "+" in the lower tab strip: the Select Report picker (Hand2Note 03 §2.2, OHM's available split types). */
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { LOWER_TAB_CAPTION, REPORT_GROUPS } from '@/lib/reports/catalog';
import type { LowerTab } from '@/lib/reports/pages';
import type { SplitType } from '@/lib/reports/types';
import { cn } from '@/lib/utils';

export default function SelectReportDialog({ open, onOpenChange, present, onPick }: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  /** Tabs the page already has (picking one just selects it). */
  present: readonly LowerTab[];
  onPick: (type: SplitType) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Select Report</DialogTitle>
          <DialogDescription>Add a split report to this page's lower tabs.</DialogDescription>
        </DialogHeader>
        <div className="grid max-h-[70dvh] grid-cols-1 gap-x-8 gap-y-6 overflow-y-auto sm:grid-cols-2 md:grid-cols-3">
          {REPORT_GROUPS.map((g) => (
            <section key={g.title} aria-labelledby={`report-group-${g.title}`} className="flex flex-col gap-1">
              <h3
                id={`report-group-${g.title}`}
                className="px-3 text-label font-medium tracking-wide text-muted-foreground uppercase"
              >
                {g.title}
              </h3>
              {g.items.map((it) => {
                const has = present.includes(it.type);
                return (
                  <button
                    key={it.type}
                    type="button"
                    onClick={() => { onPick(it.type); onOpenChange(false); }}
                    className={cn(
                      'flex flex-col items-start gap-0.5 rounded-control px-3 py-2 text-left outline-none',
                      'hover:bg-overlay-hover focus-visible:ring-2 focus-visible:ring-ring',
                    )}
                  >
                    <span className="flex items-center gap-2 text-sm font-semibold text-foreground">
                      {LOWER_TAB_CAPTION[it.type]}
                      {has && <span className="text-2xs font-normal text-subtle-foreground">on this page</span>}
                    </span>
                    <span className="max-w-64 text-xs text-muted-foreground">{it.description}</span>
                  </button>
                );
              })}
            </section>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
