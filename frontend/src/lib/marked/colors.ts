/**
 * Tailwind classes for tag / colour-marker tokens. Class strings are spelled out so Tailwind's
 * scanner sees them (no `bg-${c}` interpolation).
 */
import type { TagColor } from './types';

interface TagClasses {
  /** Solid fill (dots, swatches). */
  dot: string;
  /** Chip: text in the tag colour, 50% border, 10% fill. */
  chip: string;
}

export const TAG_CLASSES: Record<TagColor, TagClasses> = {
  'tag-1': { dot: 'bg-tag-1', chip: 'text-tag-1 border-tag-1/50 bg-tag-1/10' },
  'tag-2': { dot: 'bg-tag-2', chip: 'text-tag-2 border-tag-2/50 bg-tag-2/10' },
  'tag-3': { dot: 'bg-tag-3', chip: 'text-tag-3 border-tag-3/50 bg-tag-3/10' },
  'tag-4': { dot: 'bg-tag-4', chip: 'text-tag-4 border-tag-4/50 bg-tag-4/10' },
  'tag-5': { dot: 'bg-tag-5', chip: 'text-tag-5 border-tag-5/50 bg-tag-5/10' },
  'tag-6': { dot: 'bg-tag-6', chip: 'text-tag-6 border-tag-6/50 bg-tag-6/10' },
  'tag-7': { dot: 'bg-tag-7', chip: 'text-tag-7 border-tag-7/50 bg-tag-7/10' },
  'tag-8': { dot: 'bg-tag-8', chip: 'text-tag-8 border-tag-8/50 bg-tag-8/10' },
  'tag-9': { dot: 'bg-tag-9', chip: 'text-tag-9 border-tag-9/50 bg-tag-9/10' },
};

/** Human names for the colour picker (aria labels, tooltips). */
export const TAG_COLOR_NAMES: Record<TagColor, string> = {
  'tag-1': 'Grey',
  'tag-2': 'Blue',
  'tag-3': 'Green',
  'tag-4': 'Purple',
  'tag-5': 'Orange',
  'tag-6': 'Pink',
  'tag-7': 'Red',
  'tag-8': 'Yellow',
  'tag-9': 'Cyan',
};

export function tagClasses(color: string): TagClasses {
  return TAG_CLASSES[color as TagColor] ?? TAG_CLASSES['tag-1'];
}
