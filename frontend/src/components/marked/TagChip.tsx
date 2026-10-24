import { Chip } from '@/components/ui/chip';
import { tagClasses } from '@/lib/marked/colors';
import type { TagRef } from '@/lib/marked/types';
import { cn } from '@/lib/utils';

/** A tag as a chip in its token colour; optional click (navigate) and remove button. */
export default function TagChip({ tag, onClick, onRemove, size = 'sm', className }: {
  tag: Pick<TagRef, 'name' | 'color'>;
  onClick?: React.MouseEventHandler<HTMLButtonElement>;
  onRemove?: () => void;
  size?: 'sm' | 'md';
  className?: string;
}) {
  return (
    <Chip
      size={size}
      onClick={onClick}
      onRemove={onRemove}
      removeLabel={`Remove tag ${tag.name}`}
      className={cn('border max-w-full', tagClasses(tag.color).chip, className)}
    >
      <span className="truncate">{tag.name}</span>
    </Chip>
  );
}
