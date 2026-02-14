import { useRef, useState, useEffect } from 'react';
import type { Snapshot } from './useReplayerState';
import { getSeatPositions } from './seatLayout';
import PlayerSeat from './PlayerSeat';
import { CardBoxRow } from '../CardDisplay';

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
  const H = Math.round(W * 0.6);
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
          {/* Table oval */}
          <div
            className="absolute rounded-[50%] border-2 border-border/40"
            style={{
              left: W * 0.15,
              top: H * 0.15,
              width: W * 0.70,
              height: H * 0.70,
              backgroundColor: 'oklch(0.20 0.015 160)',
            }}
          />

          {/* Center: pot + board */}
          <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 flex flex-col items-center gap-1 z-10">
            {snapshot.board.length > 0 && (
              <CardBoxRow cards={snapshot.board} />
            )}
            {potDisplay && (
              <div className="text-[14px] font-mono font-bold text-text bg-background/70 rounded px-2 py-0.5">
                {potDisplay}
              </div>
            )}
          </div>

          {/* Dealer button */}
          {btnIdx >= 0 && seats[btnIdx] && (
            <div
              className="absolute w-[16px] h-[16px] rounded-full bg-yellow-400 text-black text-[8px] font-bold flex items-center justify-center z-20 border border-yellow-600"
              style={{
                left: seats[btnIdx].x - 8 + (seats[btnIdx].x > W / 2 ? -16 : 16),
                top: seats[btnIdx].y - 8,
              }}
            >
              D
            </div>
          )}

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
