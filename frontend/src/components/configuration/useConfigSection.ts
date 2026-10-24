import { useMemo, useRef } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { configQueryKey, getConfig, putConfig, resetConfig, type ConfigSection } from '@/lib/config/api';
import { createSaveQueue } from '@/lib/config/saveQueue';
import type { ConfigEnvelope } from '@/lib/config/types';

/** Query key of the "is a rebuild required?" health probe (RebuildBanner). */
export const rebuildRequiredQueryKey = ['health', 'rebuild-required'] as const;

/**
 * A JSON config section: the stored envelope, optimistic save-on-change and reset. Edits show at once,
 * build on the latest cached value (never a stale render), go to the server one at a time (latest wins)
 * and roll back with a toast when the server refuses. Errors toast.
 */
export function useConfigSection<T>(section: ConfigSection, opts: { invalidateAll?: boolean } = {}) {
  const qc = useQueryClient();
  const key = configQueryKey(section);
  const query = useQuery({ queryKey: key, queryFn: () => getConfig<T>(section) });
  const invalidateAll = opts.invalidateAll;

  const after = (env: ConfigEnvelope<T>) => {
    qc.setQueryData(key, env);
    void qc.invalidateQueries({ queryKey: rebuildRequiredQueryKey });
    if (invalidateAll) void qc.invalidateQueries();
  };

  // The last value the server confirmed (rollback target)
  const server = useRef<ConfigEnvelope<T> | undefined>(undefined);
  const afterRef = useRef(after);
  afterRef.current = after;

  const queue = useMemo(
    () =>
      createSaveQueue<T, ConfigEnvelope<T>>({
        send: (value) => putConfig<T>(section, value),
        onSaved: (env, more) => {
          server.current = env;
          if (more) return;
          afterRef.current(env);
        },
        onFailed: (e) => {
          toast.error('Saving failed', { description: e.message });
          if (server.current) qc.setQueryData(key, server.current);
          void qc.invalidateQueries({ queryKey: key });
        },
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [section, qc],
  );

  /** Apply `fn` to the latest value (cache, including unsaved edits), show it now and save it. */
  const update = (fn: (current: T) => T) => {
    const cur = qc.getQueryData<ConfigEnvelope<T>>(key);
    if (!cur) return;
    if (queue.idle()) server.current = cur;
    const next = fn(cur.value);
    qc.setQueryData<ConfigEnvelope<T>>(key, { ...cur, value: next });
    queue.push(next);
  };

  const reset = useMutation({ mutationFn: () => resetConfig<T>(section), onSuccess: after });

  return {
    env: query.data,
    isError: query.isError,
    error: query.error,
    update,
    save: (value: T) => update(() => value),
    reset: () => reset.mutateAsync(),
  };
}
