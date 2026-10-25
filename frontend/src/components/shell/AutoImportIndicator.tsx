import { useEffect, useRef } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { FolderSync, Settings2, Power } from 'lucide-react';
import { toast } from 'sonner';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { configQueryKey, getConfig, putConfig } from '@/lib/config/api';
import type { ConfigEnvelope } from '@/lib/config/types';
import { count, formatDateTime } from '@/lib/format';
import {
  AUTO_IMPORT_POLL_MS, AUTO_IMPORT_STATUS_KEY, getAutoImportStatus, refreshDelay, statusText,
} from '@/lib/import/auto-import';
import type { AutoImportConfig } from '@/lib/import/types';
import { refreshAfterDataChange } from '@/lib/query-policy';

/**
 * Polls the auto-import status while it is on. When it adds hands (at most every 5 s) the cheap
 * queries refresh and the heavy ones are only marked stale (lib/query-policy.ts): a visible report
 * keeps its numbers and shows the "New hands" chip instead of recomputing on every tick.
 */
function useAutoImportStatus(enabled: boolean) {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: AUTO_IMPORT_STATUS_KEY,
    queryFn: getAutoImportStatus,
    enabled,
    refetchInterval: AUTO_IMPORT_POLL_MS,
  });
  const hands = query.data?.session_hands ?? null;
  const prev = useRef<number | null>(null);
  const lastRefresh = useRef(0);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (!enabled) {
      prev.current = null;
      return;
    }
    if (hands === null) return;
    const delay = refreshDelay(prev.current, hands, lastRefresh.current, Date.now());
    prev.current = hands;
    if (delay === null) return;
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      lastRefresh.current = Date.now();
      void refreshAfterDataChange(qc, 'auto-import').catch(() => {});
    }, delay);
  }, [enabled, hands, qc]);
  useEffect(() => () => window.clearTimeout(timer.current), []);
  return query.data ?? null;
}

/** Status bar item while auto-import is on: counters, a tooltip with the last import / error, a quick toggle. */
export default function AutoImportIndicator() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const key = configQueryKey('auto_import');
  const cfg = useQuery({ queryKey: key, queryFn: () => getConfig<AutoImportConfig>('auto_import') });
  const enabled = cfg.data?.value?.enabled === true;
  const status = useAutoImportStatus(enabled);

  const turnOff = useMutation({
    mutationFn: () => putConfig<AutoImportConfig>('auto_import', { ...(cfg.data as ConfigEnvelope<AutoImportConfig>).value, enabled: false }),
    onSuccess: (env) => qc.setQueryData(key, env),
    onError: (e: Error) => toast.error('Could not turn off auto import', { description: e.message }),
  });

  if (!enabled) return null;

  const text = status ? statusText(status, count) : 'Auto import: starting…';
  const detail = status?.last_error
    ? `Error: ${status.last_error}`
    : status?.last_import_at
      ? `Last import ${formatDateTime(status.last_import_at)}`
      : 'Nothing imported yet';

  return (
    <DropdownMenu>
      <Tooltip>
        <TooltipTrigger asChild>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              aria-label={`${text}. Options`}
              className="flex items-center gap-1.5 rounded-control px-1.5 py-0.5 outline-none hover:bg-overlay-hover hover:text-foreground focus-visible:ring-2 focus-visible:ring-primary"
            >
              <FolderSync className={status?.running ? 'size-3.5 animate-pulse text-primary' : 'size-3.5'} aria-hidden />
              <span className={status?.last_error ? 'text-money-neg' : undefined}>{text}</span>
            </button>
          </DropdownMenuTrigger>
        </TooltipTrigger>
        <TooltipContent>{detail}</TooltipContent>
      </Tooltip>
      <DropdownMenuContent align="start" side="top">
        <DropdownMenuItem onSelect={() => turnOff.mutate()}>
          <Power />
          Turn off auto import
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => navigate('/configuration/auto-import')}>
          <Settings2 />
          Auto import settings…
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
