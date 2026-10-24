import type { ReactNode } from 'react';
import { CircleHelp } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

/** One setting: label (+ help tooltip, + "changed" dot) on the left, the control on the right. */
export default function OptionRow({ id, label, help, changed = false, error, children }: {
  /** Id of the control, so the label is clickable. */
  id?: string;
  label: string;
  help?: string;
  /** The value differs from its default. */
  changed?: boolean;
  error?: string | null;
  children: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-6 border-b border-border-subtle py-3 last:border-b-0">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <label htmlFor={id} className="text-sm font-medium">{label}</label>
          {changed && (
            <span className="inline-flex" title="Changed from default">
              <span aria-hidden className="size-1.5 rounded-pill bg-primary" />
              <span className="sr-only">changed from default</span>
            </span>
          )}
          {help && (
            <Tooltip>
              <TooltipTrigger asChild>
                <button type="button" aria-label={`About ${label}`} className="rounded-pill text-subtle-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-primary">
                  <CircleHelp className="size-3.5" aria-hidden />
                </button>
              </TooltipTrigger>
              <TooltipContent className="max-w-xs">{help}</TooltipContent>
            </Tooltip>
          )}
        </div>
        {error && <p role="alert" className="mt-1 text-xs text-money-neg">{error}</p>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}
