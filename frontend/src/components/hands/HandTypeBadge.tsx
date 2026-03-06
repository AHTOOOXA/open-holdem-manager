import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

export function RitBadge({ boards }: { boards: number }) {
  const label = boards >= 3 ? 'RIT3' : 'RIT';
  const tip = boards >= 3 ? 'Run It Three Times' : 'Run It Twice';
  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="text-[9px] font-bold tracking-wide text-teal-400 bg-teal-400/15 px-1 py-px rounded leading-tight">
            {label}
          </span>
        </TooltipTrigger>
        <TooltipContent side="top" className="text-xs">
          {tip}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

export function CashoutBadge() {
  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="text-[9px] font-bold tracking-wide text-amber-400 bg-amber-400/15 px-1 py-px rounded leading-tight">
            $CO
          </span>
        </TooltipTrigger>
        <TooltipContent side="top" className="text-xs">
          EV Cashout
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
