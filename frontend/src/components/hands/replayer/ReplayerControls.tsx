import { useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import {
  Play,
  Pause,
  ChevronLeft,
  ChevronRight,
  SkipBack,
  SkipForward,
} from 'lucide-react';

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
    <div className="space-y-0.5">
      {/* Progress bar — padded wrapper for larger click target */}
      <div
        className="pt-1 pb-2 cursor-pointer"
        onClick={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
          onGoToStep(Math.round(pct * totalSteps));
        }}
      >
        <div className="h-1.5 bg-border/30 rounded-full">
          <div
            className="h-full bg-primary rounded-full transition-all duration-100"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Controls row */}
      <div className="flex items-center gap-1.5">
        <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={onGoToStart}>
          <SkipBack className="w-4 h-4" />
        </Button>
        <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={onStepBack}>
          <ChevronLeft className="w-5 h-5" />
        </Button>
        <Button
          variant={isPlaying ? 'secondary' : 'default'}
          size="sm"
          className="h-8 w-10 p-0"
          onClick={onTogglePlay}
        >
          {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
        </Button>
        <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={onStepForward}>
          <ChevronRight className="w-5 h-5" />
        </Button>
        <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={onGoToEnd}>
          <SkipForward className="w-4 h-4" />
        </Button>

        <span className="text-[12px] text-text-muted font-mono ml-1">
          {streetLabel} {currentStep}/{totalSteps}
        </span>

        <div className="flex-1" />

        <ToggleGroup type="single" value={String(speed)} onValueChange={(v) => v && onSetSpeed(Number(v))} className="gap-0">
          {[1, 2, 3].map((s) => (
            <ToggleGroupItem key={s} value={String(s)} className="h-7 px-2 text-[11px]">{s}x</ToggleGroupItem>
          ))}
        </ToggleGroup>

        <ToggleGroup type="single" value={showBb ? 'bb' : 'usd'} onValueChange={(v) => v && onSetShowBb(v === 'bb')} className="gap-0">
          <ToggleGroupItem value="bb" className="h-7 px-2 text-[11px]">BB</ToggleGroupItem>
          <ToggleGroupItem value="usd" className="h-7 px-2 text-[11px]">$</ToggleGroupItem>
        </ToggleGroup>
      </div>
    </div>
  );
}
