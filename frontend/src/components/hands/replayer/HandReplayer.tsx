import { useState } from 'react';
import type { HandDetail } from '@/lib/api';
import { useReplayerState } from './useReplayerState';
import PokerTable from './PokerTable';
import ReplayerControls from './ReplayerControls';

export default function HandReplayer({ hand }: { hand: HandDetail }) {
  const [showBb, setShowBb] = useState(true);
  const replayer = useReplayerState(hand);

  return (
    <div className="space-y-3">
      <PokerTable
        snapshot={replayer.current}
        showBb={showBb}
        bbAmount={hand.bb_amount}
      />
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
