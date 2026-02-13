import PlayerTypeBadge from '@/components/PlayerTypeBadge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

interface SegmentStats {
  player_type: string;
  count: number;
  avg_hands: number;
  vpip: number | null;
  pfr: number | null;
  three_bet: number | null;
  af: number | null;
  wtsd: number | null;
  wwsf: number | null;
}

function fmt(v: number | null, decimals = 1): string {
  if (v === null || v === undefined) return '\u2014';
  return v.toFixed(decimals);
}

export default function SegmentComparison({ segments }: { segments: SegmentStats[] }) {
  if (segments.length === 0) return null;

  // Sort: NIT, TAG, LAG, REC, MAN, UNK
  const order = ['NIT', 'TAG', 'LAG', 'REC', 'MAN', 'UNK'];
  const sorted = [...segments].sort((a, b) =>
    order.indexOf(a.player_type) - order.indexOf(b.player_type)
  );

  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow className="text-[12px] uppercase tracking-wide">
            <TableHead className="py-1.5 px-2 h-auto">Type</TableHead>
            <TableHead className="py-1.5 px-2 h-auto text-right">Players</TableHead>
            <TableHead className="py-1.5 px-2 h-auto text-right">Avg Hands</TableHead>
            <TableHead className="py-1.5 px-2 h-auto text-right">VPIP</TableHead>
            <TableHead className="py-1.5 px-2 h-auto text-right">PFR</TableHead>
            <TableHead className="py-1.5 px-2 h-auto text-right">3-Bet</TableHead>
            <TableHead className="py-1.5 px-2 h-auto text-right">AF</TableHead>
            <TableHead className="py-1.5 px-2 h-auto text-right">WTSD</TableHead>
            <TableHead className="py-1.5 px-2 h-auto text-right">WWSF</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((s) => (
            <TableRow key={s.player_type} className="text-[13px]">
              <TableCell className="py-1.5 px-2">
                <PlayerTypeBadge type={s.player_type} />
              </TableCell>
              <TableCell className="py-1.5 px-2 text-right font-mono text-text-muted">
                {s.count}
              </TableCell>
              <TableCell className="py-1.5 px-2 text-right font-mono text-text-muted">
                {Math.round(s.avg_hands)}
              </TableCell>
              <TableCell className="py-1.5 px-2 text-right font-mono">{fmt(s.vpip)}</TableCell>
              <TableCell className="py-1.5 px-2 text-right font-mono">{fmt(s.pfr)}</TableCell>
              <TableCell className="py-1.5 px-2 text-right font-mono">{fmt(s.three_bet)}</TableCell>
              <TableCell className="py-1.5 px-2 text-right font-mono">{fmt(s.af, 2)}</TableCell>
              <TableCell className="py-1.5 px-2 text-right font-mono">{fmt(s.wtsd)}</TableCell>
              <TableCell className="py-1.5 px-2 text-right font-mono">{fmt(s.wwsf)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
