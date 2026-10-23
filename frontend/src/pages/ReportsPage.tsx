/**
 * Reports screen (/reports): Hand2Note-style drill-down dashboard of the active workspace.
 * Old preview links (`?tab=graph|range|hands`, `stat_flag`, `position`, `stat_key`) are consumed on
 * arrival: they pick page 0's tab (and the Hands filters), then leave the URL.
 */
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useWorkspace } from '@/contexts/WorkspaceContext';
import ReportsDashboard, { type LegacyArrival } from '@/components/reports/ReportsDashboard';
import { parseLegacyReportLink, withoutLegacyParams } from '@/lib/reports-tab';

export default function ReportsPage() {
  const { activeWorkspaceId } = useWorkspace();
  const [searchParams, setSearchParams] = useSearchParams();

  const link = parseLegacyReportLink(searchParams);
  const linkKey = link ? searchParams.toString() : null;
  const [seen, setSeen] = useState<string | null>(null);
  const [legacy, setLegacy] = useState<LegacyArrival | null>(null);
  if (linkKey !== seen) {
    setSeen(linkKey);
    if (link) setLegacy((prev) => ({ link, rev: (prev?.rev ?? 0) + 1 }));
  }

  useEffect(() => {
    if (linkKey) setSearchParams((prev) => withoutLegacyParams(prev), { replace: true });
  }, [linkKey, setSearchParams]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <ReportsDashboard key={activeWorkspaceId} workspaceId={activeWorkspaceId} legacy={legacy} />
    </div>
  );
}
