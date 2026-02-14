import { useRef, useState, useEffect } from 'react';
import type { Snapshot } from './useReplayerState';
import { getSeatPositions, getBetPosition } from './seatLayout';
import PlayerSeat from './PlayerSeat';

/* ── Action color mapping ──────────────────────────────────────────── */

const ACTION_COLORS: Record<string, string> = {
  Fold: 'text-text-muted',
  Check: 'text-text',
  Call: 'text-green',
  Bet: 'text-yellow-400',
  Raise: 'text-red',
  Won: 'text-green',
};

function getActionColor(action: string | null): string {
  if (!action) return 'text-text-muted';
  for (const [key, color] of Object.entries(ACTION_COLORS)) {
    if (action.startsWith(key)) return color;
  }
  return 'text-text';
}

/* ── Board card (larger, with suit symbol) ─────────────────────────── */

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

function BoardCard({ card }: { card: string }) {
  if (!card || card.length < 2) return null;
  const rank = card.slice(0, -1).toUpperCase();
  const suit = card.slice(-1).toLowerCase();
  const bg = SUIT_BG[suit] || 'oklch(0.268 0.007 34.298)';
  const symbol = SUIT_SYMBOL[suit] || '';
  return (
    <span
      className="inline-flex flex-col items-center justify-center w-[42px] h-[52px] rounded-[5px] text-white leading-none shrink-0 shadow-lg"
      style={{ backgroundColor: bg }}
    >
      <span className="text-[22px] font-bold leading-none">{rank}</span>
      <span className="text-[14px] leading-none opacity-80">{symbol}</span>
    </span>
  );
}

/* ── Main table component ──────────────────────────────────────────── */

export default function PokerTable({
  snapshot,
  showBb,
  bbAmount,
}: {
  snapshot: Snapshot;
  showBb: boolean;
  bbAmount: number;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(entries => {
      for (const entry of entries) {
        setWidth(entry.contentRect.width);
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const playerCount = snapshot.players.length;
  const W = width;
  const H = Math.round(W * 0.55);
  const seats = getSeatPositions(playerCount, W, H);
  const isShowdown = snapshot.streetLabel === 'Result';

  const btnIdx = snapshot.players.findIndex(p => p.position === 'BTN');

  const potDisplay = snapshot.pot > 0
    ? showBb ? `${snapshot.pot.toFixed(1)} BB` : `$${(snapshot.pot * bbAmount).toFixed(2)}`
    : '';

  return (
    <div ref={containerRef} className="relative w-full" style={{ height: H || 200 }}>
      {W === 0 ? null : (
        <>
          {/* Table oval — felt with radial gradient and rail shadow */}
          <div
            className="absolute rounded-[50%] border-[3px]"
            style={{
              left: W * 0.12,
              top: H * 0.12,
              width: W * 0.76,
              height: H * 0.76,
              background: 'radial-gradient(ellipse at 50% 40%, oklch(0.22 0.02 160), oklch(0.16 0.015 160))',
              borderColor: 'oklch(0.25 0.008 160)',
              boxShadow: 'inset 0 0 40px oklch(0.12 0.012 160 / 0.6), 0 4px 20px oklch(0.08 0 0 / 0.5)',
            }}
          />

          {/* Center: board cards + pot */}
          <div className="absolute left-1/2 top-[52%] -translate-x-1/2 -translate-y-1/2 flex flex-col items-center gap-1.5 z-10">
            {snapshot.board.length > 0 && (
              <div className="flex gap-[3px]">
                {snapshot.board.map((c, i) => (
                  <BoardCard key={i} card={c} />
                ))}
              </div>
            )}
            {potDisplay && (
              <div className="text-[15px] font-mono font-bold text-text bg-black/50 rounded-full px-4 py-0.5 backdrop-blur-sm">
                {potDisplay}
              </div>
            )}
          </div>

          {/* Dealer button is rendered inline in PlayerSeat for BTN */}

          {/* Action / bet overlays — floating between seat and table center */}
          {snapshot.players.map((player, i) => {
            const seat = seats[i];
            if (!seat) return null;

            // Determine what to show
            let showOverlay: boolean;
            if (isShowdown) {
              showOverlay = player.wonBb > 0;
            } else {
              if (player.isFolded) return null;
              showOverlay = player.lastAction !== null || player.currentBet > 0;
            }
            if (!showOverlay) return null;

            const bet = getBetPosition(seat, W, H);
            const actionVerb = player.lastAction?.split(' ')[0] || null;
            const isAllIn = player.lastAction?.includes('all-in') || false;
            const hasBet = player.currentBet > 0 && !isShowdown;
            const betDisplay = hasBet
              ? showBb ? player.currentBet.toFixed(1) : `$${(player.currentBet * bbAmount).toFixed(2)}`
              : null;

            return (
              <div
                key={`action-${player.username}`}
                className="absolute z-[15] pointer-events-none"
                style={{
                  left: bet.x,
                  top: bet.y,
                  transform: 'translate(-50%, -50%)',
                }}
              >
                <div className="flex flex-col items-center">
                  {/* Action verb */}
                  {actionVerb && (
                    <span
                      className={`text-[12px] font-semibold leading-tight ${getActionColor(player.lastAction)}`}
                      style={{ textShadow: '0 1px 3px rgba(0,0,0,0.9)' }}
                    >
                      {actionVerb}
                    </span>
                  )}
                  {/* All-in badge */}
                  {isAllIn && (
                    <span
                      className="text-[10px] font-bold text-red uppercase tracking-wider leading-tight"
                      style={{ textShadow: '0 1px 3px rgba(0,0,0,0.9)' }}
                    >
                      all-in
                    </span>
                  )}
                  {/* Bet chip */}
                  {betDisplay && (
                    <span className="text-[13px] font-mono font-bold text-yellow-400 bg-black/50 rounded-full px-2.5 py-px border border-yellow-400/30 leading-tight mt-px">
                      {betDisplay}
                    </span>
                  )}
                  {/* Showdown won */}
                  {isShowdown && player.wonBb > 0 && (
                    <span
                      className="text-[13px] font-bold text-green leading-tight"
                      style={{ textShadow: '0 1px 3px rgba(0,0,0,0.9)' }}
                    >
                      Won {showBb ? player.wonBb.toFixed(1) : `$${(player.wonBb * bbAmount).toFixed(2)}`}
                    </span>
                  )}
                </div>
              </div>
            );
          })}

          {/* Player seats */}
          {snapshot.players.map((player, i) => {
            const pos = seats[i];
            if (!pos) return null;
            return (
              <div
                key={player.username}
                className="absolute z-10"
                style={{
                  left: pos.x,
                  top: pos.y,
                  transform: 'translate(-50%, -50%)',
                }}
              >
                <PlayerSeat
                  player={player}
                  isActive={snapshot.activePlayerIdx === i}
                  isShowdown={isShowdown}
                  showBb={showBb}
                  bbAmount={bbAmount}
                />
              </div>
            );
          })}
        </>
      )}
    </div>
  );
}
