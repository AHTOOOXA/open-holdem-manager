import { Skeleton } from '@/components/ui/skeleton';

/** Shown while a screen's chunk loads (first visit only). */
export function RouteFallback() {
  return (
    <div role="status" aria-label="Loading screen" aria-busy className="flex flex-col gap-3">
      <Skeleton className="h-8 w-64" />
      <Skeleton className="h-40 w-full" />
      <Skeleton className="h-64 w-full" />
    </div>
  );
}
