import * as React from 'react';
import { format, parse } from 'date-fns';
import { CalendarIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';

interface DatePickerProps {
  value?: string; // YYYY-MM-DD string
  onChange?: (value: string) => void;
  placeholder?: string;
  className?: string;
}

export function DatePicker({ value, onChange, placeholder = 'Pick date', className }: DatePickerProps) {
  const [open, setOpen] = React.useState(false);

  // Accept both 'yyyy-MM-dd' and full ISO datetime strings (slice to date portion)
  const dateStr = value ? value.slice(0, 10) : undefined;
  const date = dateStr ? parse(dateStr, 'yyyy-MM-dd', new Date()) : undefined;

  const handleSelect = (d: Date | undefined) => {
    onChange?.(d ? format(d, 'yyyy-MM-dd') : '');
    setOpen(false);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          className={cn(
            'justify-start text-left font-normal',
            !value && 'text-muted-foreground',
            className,
          )}
        >
          <CalendarIcon className="mr-1.5 h-3.5 w-3.5 opacity-60" />
          {value ? format(date!, 'MMM d, yyyy') : <span>{placeholder}</span>}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="single"
          selected={date}
          onSelect={handleSelect}
          defaultMonth={date}
        />
      </PopoverContent>
    </Popover>
  );
}
