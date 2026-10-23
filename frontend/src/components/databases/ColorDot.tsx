import { cn } from '@/lib/utils';

export default function ColorDot({ color, className }: { color: string | null; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn('inline-block size-3 shrink-0 rounded-pill', className)}
      style={{ backgroundColor: color ?? 'var(--subtle-foreground)' }}
    />
  );
}
