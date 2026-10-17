import type { SplitRow, StrengthBucket } from '@/lib/api-general';
import { SplitTable } from './BoardsTab';
import type { SplitSelection } from './BoardsTab';

interface BetSizesTabProps {
  rows: SplitRow[];
  /** Preflop stats have no hand values: the Range column is dropped. */
  showRange: boolean;
  selection: SplitSelection | null;
  onSelectRow: (row: SplitRow) => void;
  onSelectSegment: (row: SplitRow, bucket: StrengthBucket) => void;
}

/**
 * Bet Sizes tab (H2N-COMPATIBLE-STATS.md 6.6): the stat split by the size of the measured
 * action (bet as a share of the pot, raise as a multiple, call / fold vs. the
 * villain's bet size). Same table as the Boards tab.
 */
export default function BetSizesTab(props: BetSizesTabProps) {
  return <SplitTable {...props} headerLabel="Bet Size" emptyText="No bet sizes for this stat." />;
}
