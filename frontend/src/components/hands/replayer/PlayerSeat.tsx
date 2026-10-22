import type { PlayerSnapshot } from './useReplayerState';
import { SUIT_BG, SUIT_BG_FALLBACK, SUIT_SYMBOL } from '@/lib/suits';
import { fixed } from '@/lib/format';

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
    ? `${fixed(player.stack, 1)}`
    : `$${fixed((player.stack * bbAmount), 2)}`;

  const displayName = player.isHero
    ? 'Hero'
    : player.username.length > 8
    ? '\u2026' + player.username.slice(-6)
    : player.username;

  return (
    <div className={`flex flex-col items-center gap-0.5 w-[130px] ${opacityClass}`}>
      {/* Cards */}
      <div className="flex gap-[3px] h-[44px] items-end mb-0.5">
        {isFolded && !isShowdown ? null : hasCards ? (
          <>
            <SeatCard card={player.card1!} />
            <SeatCard card={player.card2!} />
          </>
        ) : null}
      </div>

      {/* Info box — position first, then name, then stack */}
      <div className={`rounded-lg border px-2.5 py-1.5 text-center w-full bg-surface/90 backdrop-blur-sm ${borderClass}`}>
        <div className="text-[14px] font-bold text-text leading-tight flex items-center justify-center gap-1">
          {player.position}
          {player.position === 'BTN' && (
            <span className="w-[15px] h-[15px] rounded-full bg-yellow-400 text-black text-[8px] font-black inline-flex items-center justify-center shrink-0">
              D
            </span>
          )}
        </div>
        <div
          className={`text-[11px] truncate leading-tight ${player.isHero ? 'text-primary font-semibold' : 'text-text-muted'}`}
          title={player.username}
        >
          {displayName}
        </div>
        <div className="text-[12px] text-text-muted leading-tight">
          {stackDisplay}
        </div>
      </div>
    </div>
  );
}

/* ── Card variants sized for seat view ─────────────────────────────── */

function SeatCard({ card }: { card: string }) {
  if (!card || card.length < 2) return null;
  const rank = card.slice(0, -1).toUpperCase();
  const suit = card.slice(-1).toLowerCase();
  const bg = SUIT_BG[suit] ?? SUIT_BG_FALLBACK;
  const symbol = SUIT_SYMBOL[suit] || '';
  return (
    <span
      className={`inline-flex flex-col items-center justify-center w-[36px] h-[44px] rounded-[4px] text-white ${bg} leading-none shrink-0 shadow-md`}
    >
      <span className="text-[18px] font-bold leading-none">{rank}</span>
      <span className="text-[12px] leading-none opacity-80">{symbol}</span>
    </span>
  );
}
