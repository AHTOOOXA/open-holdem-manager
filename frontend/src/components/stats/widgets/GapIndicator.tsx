import type { HeroStats } from '@/lib/api';

interface Props {
  heroStats?: HeroStats;
}

export default function GapIndicator({ heroStats }: Props) {
  if (!heroStats) return null;

  const vpip = heroStats.vpip?.total?.value;
  const pfr = heroStats.pfr?.total?.value;
  if (vpip == null || pfr == null) return null;

  const gap = vpip - pfr;
  // Healthy gap is 3-8%. Too large means too passive (lots of calling).
  const color = gap <= 8 ? 'text-green' : gap <= 14 ? 'text-yellow-400' : 'text-red';

  return (
    <div>
      <div className="text-[11px] text-muted-foreground mb-0.5">VPIP-PFR Gap</div>
      <div className="flex items-baseline gap-2">
        <span className={`text-lg font-bold ${color}`}>{gap.toFixed(1)}%</span>
        <span className="text-[10px] text-muted-foreground">
          ({vpip.toFixed(1)} - {pfr.toFixed(1)})
        </span>
      </div>
    </div>
  );
}
