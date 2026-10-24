import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { DatePicker } from '@/components/ui/date-picker';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useImport } from '@/contexts/ImportContext';
import { useDayStartHour } from '@/hooks/useDayStart';
import {
  filterMode, importPresets, isValidFilter, loadFilter, resolveFilter, saveFilter,
} from '@/lib/import/date-filter';
import type { ImportDateFilter } from '@/lib/import/types';
import { formatMediumDate } from '@/lib/format';

const storage = () => (typeof localStorage === 'undefined' ? null : localStorage);

/** "Import Hand History": the one step before every manual import. Only the date range is chosen here. */
export default function ImportHandHistoryDialog() {
  const { pendingSource, cancelPendingImport } = useImport();
  return (
    <Dialog open={pendingSource !== null} onOpenChange={(o) => !o && cancelPendingImport()}>
      <DialogContent className="sm:max-w-md">
        {/* Mounted only while open: the last filter is read fresh each time */}
        <FilterStep />
      </DialogContent>
    </Dialog>
  );
}

function FilterStep() {
  const { confirmPendingImport, cancelPendingImport } = useImport();
  const dayStart = useDayStartHour();
  const [filter, setFilter] = useState<ImportDateFilter>(() => loadFilter(storage(), new Date(), dayStart));
  // "Custom" with no dates yet must stay selected
  const [custom, setCustom] = useState(() => filterMode(filter) === 'custom');

  const presets = importPresets(new Date(), dayStart);
  const mode = custom ? 'custom' : filterMode(filter);
  const resolved = resolveFilter(filter, new Date(), dayStart);
  const valid = isValidFilter(filter);

  const pick = (value: string) => {
    if (value === 'all') {
      setCustom(false);
      setFilter({});
    } else if (value === 'custom') {
      setCustom(true);
      setFilter((f) => ({ from: f.from, to: f.to }));
    } else {
      setCustom(false);
      setFilter({ preset: value });
    }
  };

  const apply = () => {
    saveFilter(storage(), filter);
    confirmPendingImport(resolveFilter(filter, new Date(), dayStart));
  };

  return (
    <>
    <DialogHeader>
      <DialogTitle>Import Hand History</DialogTitle>
      <DialogDescription>Only hands played in this period are imported.</DialogDescription>
    </DialogHeader>
    <div className="flex flex-col gap-3">
      <label className="flex flex-col gap-1.5 text-sm text-muted-foreground">
        Date range
        <Select value={mode} onValueChange={pick}>
          <SelectTrigger className="w-full" aria-label="Date range">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Time</SelectItem>
            {presets.map((p) => (
              <SelectItem key={p.id} value={p.id}>{p.label}</SelectItem>
            ))}
            <SelectItem value="custom">Custom range</SelectItem>
          </SelectContent>
        </Select>
      </label>
      {mode === 'custom' && (
        <div className="flex items-center gap-2">
          <DatePicker value={filter.from} onChange={(v) => setFilter((f) => ({ ...f, from: v || undefined }))} placeholder="From" className="flex-1" />
          <DatePicker value={filter.to} onChange={(v) => setFilter((f) => ({ ...f, to: v || undefined }))} placeholder="To" className="flex-1" />
        </div>
      )}
      {!valid && <p role="alert" className="text-xs text-money-neg">The start date is after the end date.</p>}
      {mode !== 'all' && mode !== 'custom' && resolved.date_from && (
        <p className="text-xs text-muted-foreground">
          {formatMediumDate(resolved.date_from)}
          {resolved.date_to && resolved.date_to !== resolved.date_from ? ` – ${formatMediumDate(resolved.date_to)}` : ''}
        </p>
      )}
    </div>
    <DialogFooter className="sm:justify-between">
      <Button variant="ghost" onClick={cancelPendingImport}>Cancel</Button>
      <div className="flex gap-2">
        <Button variant="outline" onClick={() => { setCustom(false); setFilter({}); }}>Reset</Button>
        <Button onClick={apply} disabled={!valid}>Apply</Button>
      </div>
    </DialogFooter>
    </>
  );
}
