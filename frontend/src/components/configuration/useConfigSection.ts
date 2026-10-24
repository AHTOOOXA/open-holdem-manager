import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { configQueryKey, getConfig, putConfig, resetConfig, type ConfigSection } from '@/lib/config/api';
import type { ConfigEnvelope } from '@/lib/config/types';

/** Query key of the "is a rebuild required?" health probe (RebuildBanner). */
export const rebuildRequiredQueryKey = ['health', 'rebuild-required'] as const;

/** A JSON config section: the stored envelope, save-on-change and reset. Errors toast. */
export function useConfigSection<T>(section: ConfigSection, opts: { invalidateAll?: boolean } = {}) {
  const qc = useQueryClient();
  const key = configQueryKey(section);
  const query = useQuery({ queryKey: key, queryFn: () => getConfig<T>(section) });

  const after = (env: ConfigEnvelope<T>) => {
    qc.setQueryData(key, env);
    void qc.invalidateQueries({ queryKey: rebuildRequiredQueryKey });
    if (opts.invalidateAll) void qc.invalidateQueries();
  };

  const save = useMutation({
    mutationFn: (value: T) => putConfig<T>(section, value),
    onSuccess: after,
    onError: (e: Error) => {
      toast.error('Saving failed', { description: e.message });
      void qc.invalidateQueries({ queryKey: key });
    },
  });
  const reset = useMutation({ mutationFn: () => resetConfig<T>(section), onSuccess: after });

  return {
    env: query.data,
    isError: query.isError,
    error: query.error,
    save: (value: T) => save.mutate(value),
    reset: () => reset.mutateAsync(),
  };
}
