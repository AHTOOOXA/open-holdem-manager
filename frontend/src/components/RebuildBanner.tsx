import { useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useLocation } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import ConfirmDialog from '@/components/databases/ConfirmDialog';
import { rebuildRequiredQueryKey } from '@/components/configuration/useConfigSection';
import { useImport } from '@/contexts/ImportContext';
import { useWorkspace } from '@/contexts/WorkspaceContext';
import { getHealth } from '@/lib/api';
import { showsRebuildBanner } from '@/lib/rebuild-banner';
import { grouped } from '@/lib/format';

/** "Rebuilding stats is required" bar on Reports, Statistics, Sessions and Configuration. */
export default function RebuildBanner() {
  const { pathname } = useLocation();
  const { phase, startRebuild } = useImport();
  const { totalHands } = useWorkspace();
  const [asking, setAsking] = useState(false);
  const { data } = useQuery({
    queryKey: rebuildRequiredQueryKey,
    queryFn: getHealth,
    refetchOnWindowFocus: true,
    retry: false,
  });

  if (!showsRebuildBanner(pathname, data?.rebuild_required === true, phase === 'rebuilding' || data?.rebuilding === true)) return null;

  return (
    <div role="status" className="flex items-center gap-3 border-b border-primary bg-primary/10 px-4 py-2 text-sm">
      <RefreshCw className="size-4 shrink-0 text-primary" aria-hidden />
      <div className="min-w-0 flex-1">
        <span className="font-medium">Rebuilding stats is required</span>
        <span className="text-muted-foreground"> · A setting that stored stats depend on changed (for example the 'Who is regular?' rule).</span>
      </div>
      <Button size="sm" disabled={phase !== 'idle'} onClick={() => setAsking(true)}>Rebuild stats</Button>
      <ConfirmDialog
        open={asking}
        title="Rebuild statistics?"
        description={`Recomputes every stat for all ${grouped(totalHands)} stored hands. The app stays usable while it runs; progress shows in the status bar.`}
        confirmLabel="Rebuild"
        onConfirm={() => {
          setAsking(false);
          startRebuild();
        }}
        onCancel={() => setAsking(false)}
      />
    </div>
  );
}
