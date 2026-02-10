import { useQuery } from '@tanstack/react-query';
import { getFilterOptions } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';

export function useFilterOptions() {
  return useQuery({
    queryKey: queryKeys.filterOptions,
    queryFn: getFilterOptions,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}
