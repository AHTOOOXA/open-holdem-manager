import { useState } from 'react';
import type { HandDetail } from '@/lib/api';
import { useReplayerState } from './useReplayerState';
import PokerTable from './PokerTable';
import ReplayerControls from './ReplayerControls';

export default function HandReplayer({ hand }: { hand: HandDetail }) {
  const [showBb, setShowBb] = useState(true);
  const replayer = useReplayerState(hand);

  const hero = hand.players.find(p => p.is_hero);
  const heroWonBb = hero?.won_bb ?? 0;

  return (
    <div className="space-y-2">
      <PokerTable
        snapshot={replayer.current}
        showBb={showBb}
        bbAmount={hand.bb_amount}
      />
      {/* Result summary */}
      <div className={`text-[14px] font-bold font-mono ${heroWonBb >= 0 ? 'text-green' : 'text-red'}`}>
        Hero {heroWonBb >= 0 ? 'wins' : 'loses'} {Math.abs(heroWonBb).toFixed(1)} BB
      </div>
      <ReplayerControls
        currentStep={replayer.currentStep}
        totalSteps={replayer.snapshots.length - 1}
        isPlaying={replayer.isPlaying}
        speed={replayer.speed}
        streetLabel={replayer.current.streetLabel}
        showBb={showBb}
        onTogglePlay={replayer.togglePlay}
        onStepForward={replayer.stepForward}
        onStepBack={replayer.stepBack}
        onGoToStart={replayer.goToStart}
        onGoToEnd={replayer.goToEnd}
        onGoToStep={replayer.goToStep}
        onSetSpeed={replayer.setSpeed}
        onSetShowBb={setShowBb}
      />
    </div>
  );
}
