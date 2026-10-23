import HandExplorer from '@/components/hands/HandExplorer';
import { ANY_TAG } from '@/components/hands/HandFilters';

export default function MarkedHandsPage() {
  return (
    <HandExplorer
      initialFilters={{ tags: [ANY_TAG] }}
      emptyMessage="No marked hands yet. Open a hand and add a tag in its detail panel to see it here."
      header={
        <div className="mb-2">
          <h1 className="text-xl font-bold text-text">Marked Hands</h1>
          <p className="text-sm text-text-muted">Hands you have tagged.</p>
        </div>
      }
      className="max-w-[1600px] mx-auto px-2"
    />
  );
}
