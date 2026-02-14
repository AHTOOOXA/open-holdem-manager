import type { PlayerSnapshot } from './useReplayerState';

export default function PlayerSeat({
  player,
  isActive,
  isShowdown,
  showBb,
  bbAmount,
}: {
  player: PlayerSnapshot;
  isActive: boolean;
  isShowdown: boolean;
  showBb: boolean;
  bbAmount: number;
}) {
  const isFolded = player.isFolded;
  const isWinner = isShowdown && player.wonBb > 0;
  const hasCards = player.card1 && player.card2;

  const borderClass = isActive
    ? 'ring-2 ring-white/70'
    : isWinner
    ? 'ring-2 ring-green'
    : player.isHero
    ? 'border-primary/60'
    : 'border-border/40';

  const opacityClass = isFolded && !isShowdown ? 'opacity-25' : '';

  const stackDisplay = showBb
    ? `${player.stack.toFixed(1)}`
    : `$${(player.stack * bbAmount).toFixed(2)}`;

  // Show tail of username for non-hero (hashes are more distinguishable by suffix)
  const displayName = player.isHero
    ? 'Hero'
    : player.username.length > 8
    ? '\u2026' + player.username.slice(-6)
    : player.username;

  return (
    <div className={`flex flex-col items-center gap-0.5 w-[130px] ${opacityClass}`}>
      {/* Cards — fixed height slot to prevent wobble when cards appear/disappear */}
      <div className="flex gap-[3px] h-[44px] items-end mb-0.5">
        {isFolded && !isShowdown ? null : hasCards ? (
          <>
            <SeatCard card={player.card1!} />
            <SeatCard card={player.card2!} />
          </>
        ) : null}
      </div>

      {/* Info box — name, position, stack only */}
      <div className={`rounded-lg border px-2.5 py-1.5 text-center w-full bg-surface/90 backdrop-blur-sm ${borderClass}`}>
        <div className="flex items-center justify-center gap-1">
          <span
            className={`text-[14px] font-semibold truncate leading-tight ${
              player.isHero ? 'text-primary' : 'text-text'
            }`}
            title={player.username}
          >
            {displayName}
          </span>
          <span className="text-[11px] font-mono text-text-muted bg-surface-hover rounded px-1 leading-tight">
            {player.position}
          </span>
        </div>
        <div className="text-[13px] font-mono text-text-muted leading-tight">
          {stackDisplay}
        </div>
      </div>
    </div>
  );
}

/* ── Card variants sized for seat view ─────────────────────────────── */

const SUIT_BG: Record<string, string> = {
  s: 'oklch(0.268 0.007 34.298)',
  h: '#dc2626',
  d: '#2563eb',
  c: '#16a34a',
};

const SUIT_SYMBOL: Record<string, string> = {
  s: '\u2660',
  h: '\u2665',
  d: '\u2666',
  c: '\u2663',
};

function SeatCard({ card }: { card: string }) {
  if (!card || card.length < 2) return null;
  const rank = card.slice(0, -1).toUpperCase();
  const suit = card.slice(-1).toLowerCase();
  const bg = SUIT_BG[suit] || 'oklch(0.268 0.007 34.298)';
  const symbol = SUIT_SYMBOL[suit] || '';
  return (
    <span
      className="inline-flex flex-col items-center justify-center w-[36px] h-[44px] rounded-[4px] text-white leading-none shrink-0 shadow-md"
      style={{ backgroundColor: bg }}
    >
      <span className="text-[18px] font-bold leading-none">{rank}</span>
      <span className="text-[12px] leading-none opacity-80">{symbol}</span>
    </span>
  );
}
