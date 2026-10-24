import { Checkbox } from '@/components/ui/checkbox';
import { gridColumnCount, TAGS_PER_COLUMN } from '@/lib/marked/logic';
import { tagClasses } from '@/lib/marked/colors';
import type { TagDef } from '@/lib/marked/types';
import { cn } from '@/lib/utils';

/** Tag checkboxes (colour dot + name) laid out in columns of ten, column-major. */
export default function TagCheckboxGrid({ tags, selected, onToggle, disabled }: {
  tags: readonly TagDef[];
  selected: readonly number[];
  onToggle: (id: number, on: boolean) => void;
  disabled?: boolean;
}) {
  const cols = gridColumnCount(tags.length);
  return (
    <div
      role="group"
      aria-label="Tags"
      className="grid grid-flow-col gap-x-4 gap-y-0.5"
      style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, auto))`, gridTemplateRows: `repeat(${Math.min(tags.length, TAGS_PER_COLUMN)}, auto)` }}
    >
      {tags.map((t) => (
        <label key={t.id} className={cn('flex h-row cursor-pointer items-center gap-2 text-sm', disabled && 'cursor-default opacity-60')}>
          <Checkbox checked={selected.includes(t.id)} disabled={disabled} onCheckedChange={(c) => onToggle(t.id, c === true)} />
          <span aria-hidden className={cn('size-2.5 shrink-0 rounded-pill', tagClasses(t.color).dot)} />
          <span className="truncate">{t.name}</span>
        </label>
      ))}
    </div>
  );
}
