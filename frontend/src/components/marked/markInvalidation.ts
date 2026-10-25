import type { HandListParams } from '@/lib/api';

/**
 * Does a cached hand list (['hands','list', params]) change when a hand is marked, tagged or unmarked, beyond the
 * row patch? Only when the mark decides which rows it holds (marked / tag filter) or their order (tags sort).
 * Every other list keeps its rows and order; useMarkHand patches the row's mark and tags in place.
 */
export function listDependsOnMarks(params: Partial<HandListParams> | undefined): boolean {
  if (!params) return false;
  return params.marked != null || (params.tag_ids?.length ?? 0) > 0 || params.sort === 'tags';
}
