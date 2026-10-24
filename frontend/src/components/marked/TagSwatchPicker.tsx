import { Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { TAG_COLOR_NAMES, tagClasses } from '@/lib/marked/colors';
import { TAG_COLORS } from '@/lib/marked/types';
import type { TagColor } from '@/lib/marked/types';
import { cn } from '@/lib/utils';

/** A colour swatch button that opens the 9 tag-token colours. Used by tags and colour markers. */
export default function TagSwatchPicker({ value, onChange, label }: {
  value: TagColor;
  onChange: (c: TagColor) => void;
  /** Accessible name of the trigger, e.g. "Colour of raise". */
  label: string;
}) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="h-control gap-2 px-2" aria-label={`${label}: ${TAG_COLOR_NAMES[value]}`}>
          <span className={cn('size-4 rounded-pill', tagClasses(value).dot)} aria-hidden />
          <span className="text-xs text-muted-foreground">{TAG_COLOR_NAMES[value]}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-2" align="start">
        <div role="radiogroup" aria-label={label} className="grid grid-cols-3 gap-1">
          {TAG_COLORS.map((c) => (
            <button
              key={c}
              type="button"
              role="radio"
              aria-checked={c === value}
              aria-label={TAG_COLOR_NAMES[c]}
              title={TAG_COLOR_NAMES[c]}
              onClick={() => onChange(c)}
              className="flex size-8 items-center justify-center rounded-control outline-none hover:bg-overlay-hover focus-visible:ring-2 focus-visible:ring-primary"
            >
              <span className={cn('flex size-5 items-center justify-center rounded-pill', tagClasses(c).dot)}>
                {c === value && <Check className="size-3.5 text-background" aria-hidden />}
              </span>
            </button>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}
