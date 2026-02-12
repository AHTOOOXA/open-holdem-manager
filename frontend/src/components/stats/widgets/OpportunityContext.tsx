import type { HeroStats, StatValue } from '@/lib/api';

interface Props {
  statKey: string;
  heroStats?: HeroStats;
}

export default function OpportunityContext({ statKey, heroStats }: Props) {
  if (!heroStats) return null;

  const stat = heroStats[statKey as keyof HeroStats] as StatValue | undefined;
  if (!stat || typeof stat !== 'object' || !('value' in stat)) return null;
  if (stat.value == null || stat.sample === 0) return null;

  const hands = heroStats.hands;
  const oppRate = hands > 0 ? (stat.sample / hands * 100).toFixed(1) : '0';
  const usedRate = stat.value.toFixed(1);

  return (
    <div>
      <div className="text-[11px] text-muted-foreground mb-0.5">Opportunity Context</div>
      <div className="text-[11px] text-foreground/80">
        Opportunity in <span className="font-medium">{oppRate}%</span> of hands ({stat.sample}/{hands}),
        used <span className="font-medium">{usedRate}%</span>
      </div>
    </div>
  );
}
