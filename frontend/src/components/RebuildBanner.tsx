import { useImport } from '@/contexts/ImportContext';
import { Progress } from '@/components/ui/progress';
import { useState, useRef, useEffect } from 'react';

export default function RebuildBanner() {
  const { phase, autoRebuildProgress } = useImport();
  const [hps, setHps] = useState(0);
  const prevRef = useRef<{ processed: number; time: number } | null>(null);

  useEffect(() => {
    if (!autoRebuildProgress) return;
    const now = Date.now();
    const prev = prevRef.current;
    if (prev) {
      const dt = (now - prev.time) / 1000;
      const dp = autoRebuildProgress.processed - prev.processed;
      if (dt > 0 && dp > 0) {
        setHps(Math.round(dp / dt));
      }
    }
    prevRef.current = { processed: autoRebuildProgress.processed, time: now };
  }, [autoRebuildProgress]);

  if (phase !== 'rebuilding' || !autoRebuildProgress) return null;

  const { processed, total } = autoRebuildProgress;
  const pct = total > 0 ? Math.round((processed / total) * 100) : 0;

  return (
    <div className="sticky bottom-0 flex items-center gap-3 border-t border-border bg-surface px-4 py-1.5 text-xs text-muted-foreground">
      <span className="shrink-0">Upgrading stats...</span>
      <Progress value={pct} className="h-1.5 max-w-48" />
      <span className="shrink-0 tabular-nums">
        {processed.toLocaleString()} / {total.toLocaleString()}
        {hps > 0 && ` (${hps.toLocaleString()} h/s)`}
      </span>
    </div>
  );
}
