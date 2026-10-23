import { useSearchParams } from 'react-router-dom';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Chip } from '@/components/ui/chip';
import GraphPage from '@/pages/GraphPage';
import RangePage from '@/pages/RangePage';
import HandsPage from '@/pages/HandsPage';
import { parseReportTab, withReportTab } from '@/lib/reports-tab';

export default function ReportsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = parseReportTab(searchParams.get('tab'));

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <Tabs
          value={tab}
          onValueChange={(v) => setSearchParams(withReportTab(searchParams, parseReportTab(v)), { replace: true })}
        >
          <TabsList variant="line">
            <TabsTrigger value="graph">Graph</TabsTrigger>
            <TabsTrigger value="range">Preflop Range</TabsTrigger>
            <TabsTrigger value="hands">Hands</TabsTrigger>
          </TabsList>
        </Tabs>
        <span className="flex items-center gap-2 text-xs text-text-muted">
          <Chip>Preview</Chip>
          <span className="hidden md:inline">Drill-down reports arrive in a later version</span>
        </span>
      </div>
      {tab === 'graph' && <GraphPage />}
      {tab === 'range' && <RangePage />}
      {tab === 'hands' && <HandsPage />}
    </div>
  );
}
