import { QueryClient } from '@tanstack/react-query';
import { HEAVY_GC_MS, HEAVY_KEY_PREFIXES } from './query-policy';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 2 * 60 * 1000,   // 2 minutes
      gcTime: 10 * 60 * 1000,     // 10 minutes
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

// Heavy payloads (a Graph or Split response is megabytes of parsed objects at 200k hands) leave
// the renderer heap a minute after their screen is gone, and a failed seconds-long request is not
// repeated automatically. Policy and the meta flag for new heavy queries: ./query-policy.ts
for (const prefix of HEAVY_KEY_PREFIXES) {
  queryClient.setQueryDefaults([...prefix], { gcTime: HEAVY_GC_MS, retry: 0 });
}
