import { useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';

interface ReplayerControlsProps {
  currentStep: number;
  totalSteps: number;
  isPlaying: boolean;
  speed: number;
  streetLabel: string;
  showBb: boolean;
  onTogglePlay: () => void;
  onStepForward: () => void;
  onStepBack: () => void;
  onGoToStart: () => void;
  onGoToEnd: () => void;
  onGoToStep: (step: number) => void;
  onSetSpeed: (speed: number) => void;
  onSetShowBb: (showBb: boolean) => void;
}

export default function ReplayerControls({
  currentStep,
  totalSteps,
  isPlaying,
  speed,
  streetLabel,
  showBb,
  onTogglePlay,
  onStepForward,
  onStepBack,
  onGoToStart,
  onGoToEnd,
  onGoToStep,
  onSetSpeed,
  onSetShowBb,
}: ReplayerControlsProps) {
  const handleKey = useCallback(
    (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      switch (e.key) {
        case ' ':
          e.preventDefault();
          onTogglePlay();
          break;
        case 'ArrowLeft':
          e.preventDefault();
          onStepBack();
          break;
        case 'ArrowRight':
          e.preventDefault();
          onStepForward();
          break;
        case 'Home':
          e.preventDefault();
          onGoToStart();
          break;
        case 'End':
          e.preventDefault();
          onGoToEnd();
          break;
      }
    },
    [onTogglePlay, onStepForward, onStepBack, onGoToStart, onGoToEnd],
  );

  useEffect(() => {
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [handleKey]);

  const progress = totalSteps > 0 ? (currentStep / totalSteps) * 100 : 0;

  return (
    <div className="space-y-1.5">
      {/* Progress bar */}
      <div
        className="h-1 bg-border/30 rounded-full cursor-pointer"
        onClick={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const pct = (e.clientX - rect.left) / rect.width;
          onGoToStep(Math.round(pct * totalSteps));
        }}
      >
        <div
          className="h-full bg-primary rounded-full transition-all duration-100"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Controls row */}
      <div className="flex items-center gap-1.5">
        <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-xs" onClick={onGoToStart}>&#x23EE;</Button>
        <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-xs" onClick={onStepBack}>&#x23F4;</Button>
        <Button
          variant={isPlaying ? 'secondary' : 'default'}
          size="sm"
          className="h-7 w-10 p-0 text-xs"
          onClick={onTogglePlay}
        >
          {isPlaying ? '\u275A\u275A' : '\u25B6'}
        </Button>
        <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-xs" onClick={onStepForward}>&#x23F5;</Button>
        <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-xs" onClick={onGoToEnd}>&#x23ED;</Button>

        <span className="text-[11px] text-text-muted font-mono ml-1">
          {streetLabel} {currentStep}/{totalSteps}
        </span>

        <div className="flex-1" />

        <ToggleGroup type="single" value={String(speed)} onValueChange={(v) => v && onSetSpeed(Number(v))} className="gap-0">
          {[1, 2, 3].map((s) => (
            <ToggleGroupItem key={s} value={String(s)} className="h-6 px-1.5 text-[10px]">{s}x</ToggleGroupItem>
          ))}
        </ToggleGroup>

        <ToggleGroup type="single" value={showBb ? 'bb' : 'usd'} onValueChange={(v) => v && onSetShowBb(v === 'bb')} className="gap-0">
          <ToggleGroupItem value="bb" className="h-6 px-1.5 text-[10px]">BB</ToggleGroupItem>
          <ToggleGroupItem value="usd" className="h-6 px-1.5 text-[10px]">$</ToggleGroupItem>
        </ToggleGroup>
      </div>
    </div>
  );
}
