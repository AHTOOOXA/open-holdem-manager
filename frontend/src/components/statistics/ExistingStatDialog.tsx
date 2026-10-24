/**
 * "Existing Stat…": pick one action stat of the General screen to make the dashboard a
 * single-stat dashboard. Search by name, category tabs with counts, one click picks.
 */
import { useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import {
  PICKABLE_STATS, STAT_CATEGORIES, categoryCounts, filterStats, type StatCategory,
} from '@/lib/statistics/categories';

interface ExistingStatDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Currently shown stat (highlighted), if the dashboard is a single-stat one. */
  currentId?: string | null;
  onPick: (cellId: string) => void;
}

export default function ExistingStatDialog({ open, onOpenChange, currentId, onPick }: ExistingStatDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Existing Stat</DialogTitle>
          <DialogDescription className="sr-only">Pick the stat this dashboard shows.</DialogDescription>
        </DialogHeader>
        {/* Mounted only while open: search and tab start fresh each time */}
        {open && <Picker currentId={currentId ?? null} onPick={(id) => { onPick(id); onOpenChange(false); }} />}
      </DialogContent>
    </Dialog>
  );
}

function Picker({ currentId, onPick }: { currentId: string | null; onPick: (id: string) => void }) {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState<StatCategory>('all');

  const matching = useMemo(() => filterStats(PICKABLE_STATS, search), [search]);
  const counts = useMemo(() => categoryCounts(matching), [matching]);
  const list = useMemo(() => matching.filter((s) => s.categories.includes(category)), [matching, category]);

  return (
    <div className="flex min-w-0 flex-col gap-3">
      <Input
        autoFocus
        type="search"
        aria-label="Search stats"
        placeholder="Search Stat by Name..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && list[0]) {
            e.preventDefault();
            onPick(list[0].id);
          }
        }}
      />
      <Tabs value={category} onValueChange={(v) => setCategory(v as StatCategory)}>
        <TabsList variant="line" overflow aria-label="Stat category">
          {STAT_CATEGORIES.map((c) => (
            <TabsTrigger key={c.id} value={c.id} count={counts[c.id]}>
              {c.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      <ScrollArea className="h-96 rounded-control border border-border-subtle">
        <ul aria-label="Stats" className="flex flex-col p-1">
          {list.length === 0 && <li className="px-3 py-2 text-sm text-subtle-foreground">No stats found</li>}
          {list.map((s) => (
            <li key={s.id}>
              <Button
                variant="ghost"
                aria-current={s.id === currentId || undefined}
                onClick={() => onPick(s.id)}
                className={cn(
                  'h-row w-full justify-between gap-3 rounded-control px-3 font-normal',
                  s.id === currentId && 'bg-overlay-selected',
                )}
              >
                <span className="truncate">{s.label}</span>
                <span className="shrink-0 text-xs text-subtle-foreground">{s.street === 'preflop' ? 'Preflop' : 'Postflop'}</span>
              </Button>
            </li>
          ))}
        </ul>
      </ScrollArea>
    </div>
  );
}
