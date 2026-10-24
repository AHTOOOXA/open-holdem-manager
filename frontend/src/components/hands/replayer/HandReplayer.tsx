import { useState } from 'react';
import type { HandDetail } from '@/lib/api';
import { useReplayerState } from './useReplayerState';
import PokerTable from './PokerTable';
import ReplayerControls from './ReplayerControls';
import { fixed } from '@/lib/format';
import { QUICK_REPLAY_STEP_MS } from '@/lib/hands/gestures';

export default function HandReplayer({
  hand,
  quick = false,
  onManualControl,
}: {
  hand: HandDetail;
  /** Quick-replay mode: starts playing, one step per QUICK_REPLAY_STEP_MS, no document-level keys; any control stops it. */
  quick?: boolean;
  onManualControl?: () => void;
}) {
  const [showBb, setShowBb] = useState(true);
  const replayer = useReplayerState(hand, quick ? { autoPlay: true, stepMs: QUICK_REPLAY_STEP_MS } : undefined);
  // Any manual control stops the auto-play first, then does its own thing
  const manual = <A extends unknown[]>(fn: (...args: A) => void) => (...args: A) => {
    if (quick) {
      replayer.pause();
      onManualControl?.();
    }
    fn(...args);
  };

  const hero = hand.players.find(p => p.is_hero);
  const heroWonBb = hero?.won_bb ?? 0;

  return (
    <div className="space-y-2">
      {/* RIT / Cashout indicator banners */}
      {(hand.rit_boards > 1 || hand.is_cashout) && (
        <div className="flex gap-2">
          {hand.rit_boards > 1 && (
            <div className="text-[12px] font-semibold px-2.5 py-0.5 rounded bg-teal-500/15 text-teal-400 border border-teal-500/25">
              {hand.rit_boards === 2 ? 'Run It Twice' : `Run It ${hand.rit_boards} Times`}
            </div>
          )}
          {hand.is_cashout && (
            <div className="text-[12px] font-semibold px-2.5 py-0.5 rounded bg-amber-500/15 text-amber-400 border border-amber-500/25">
              EV Cashout Hand
            </div>
          )}
        </div>
      )}
      <PokerTable
        snapshot={replayer.current}
        showBb={showBb}
        bbAmount={hand.bb_amount}
        isCashout={hand.is_cashout}
      />
      {/* Result summary */}
      <div className={`text-[14px] font-bold ${heroWonBb >= 0 ? 'text-green' : 'text-red'}`}>
        Hero {heroWonBb >= 0 ? 'wins' : 'loses'} {fixed(Math.abs(heroWonBb), 1)} BB
        {hand.is_cashout && <span className="text-amber-400 ml-1">(EV Cashout)</span>}
      </div>
      <ReplayerControls
        currentStep={replayer.currentStep}
        totalSteps={replayer.snapshots.length - 1}
        isPlaying={replayer.isPlaying}
        speed={replayer.speed}
        streetLabel={replayer.current.streetLabel}
        showBb={showBb}
        onTogglePlay={replayer.togglePlay}
        onStepForward={manual(replayer.stepForward)}
        onStepBack={manual(replayer.stepBack)}
        onGoToStart={manual(replayer.goToStart)}
        onGoToEnd={manual(replayer.goToEnd)}
        onGoToStep={manual(replayer.goToStep)}
        onSetSpeed={manual(replayer.setSpeed)}
        onSetShowBb={setShowBb}
        keyboard={!quick}
      />
    </div>
  );
}
