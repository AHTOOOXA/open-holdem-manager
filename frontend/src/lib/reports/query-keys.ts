/** react-query keys of the Reports screen. Everything starts with "reports" so Refresh can invalidate it at once. */
import { queryKeyOf } from './api';
import type { ReportQuery, SplitType } from './types';

export const reportKeys = {
  all: ['reports'] as const,
  split: (type: SplitType, q: ReportQuery) => ['reports', 'split', type, queryKeyOf(q)] as const,
  spot: (q: ReportQuery) => ['reports', 'spot', queryKeyOf(q)] as const,
};
