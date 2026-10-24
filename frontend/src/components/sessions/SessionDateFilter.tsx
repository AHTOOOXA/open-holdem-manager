/** "Date Range" popover of the session list: All Time, the presets (no "Last Session"), a custom range. */
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { DatePicker } from '@/components/ui/date-picker';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Separator } from '@/components/ui/separator';
import { datePresets, dateFilterLabel, type StoredDateFilter } from '@/lib/sessions/date-filter';
import { cn } from '@/lib/utils';

export default function SessionDateFilter({ value, onChange, dayStartHour }: {
  value: StoredDateFilter;
  onChange: (next: StoredDateFilter) => void;
  dayStartHour: number;
}) {
  const [open, setOpen] = useState(false);
  const [from, setFrom] = useState(value?.kind === 'custom' ? value.from ?? '' : '');
  const [to, setTo] = useState(value?.kind === 'custom' ? value.to ?? '' : '');
  const now = new Date();
  const presets = datePresets(now, dayStartHour);
  const active = value !== null;

  const choose = (next: StoredDateFilter) => {
    onChange(next);
    setOpen(false);
  };
  const itemClass = (selected: boolean) => cn('justify-start font-normal', selected && 'bg-overlay-selected text-primary');

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          aria-label={`Date Range: ${dateFilterLabel(value, now, dayStartHour)}`}
          className={cn(active && 'border-primary bg-overlay-selected font-semibold text-primary')}
        >
          {dateFilterLabel(value, now, dayStartHour)}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="flex w-64 flex-col gap-1 p-2">
        <Button variant="ghost" size="sm" className={itemClass(value === null)} onClick={() => choose(null)}>
          All Time
        </Button>
        {presets.map((p) => (
          <Button
            key={p.id}
            variant="ghost"
            size="sm"
            className={itemClass(value?.kind === 'preset' && value.id === p.id)}
            onClick={() => choose({ kind: 'preset', id: p.id })}
          >
            {p.label}
          </Button>
        ))}
        <Separator className="my-1" />
        <div className="flex flex-col gap-2 px-1 pb-1">
          <span className="text-label text-muted-foreground">Custom range</span>
          <DatePicker value={from} onChange={setFrom} placeholder="From" />
          <DatePicker value={to} onChange={setTo} placeholder="To" />
          <Button
            size="sm"
            disabled={!from && !to}
            onClick={() => choose({ kind: 'custom', from: from || undefined, to: to || undefined })}
          >
            Apply
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
