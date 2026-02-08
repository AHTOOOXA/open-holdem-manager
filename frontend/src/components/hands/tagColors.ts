const TAG_COLORS: Record<string, string> = {
  mistake: '#ef4444',
  bluff: '#f97316',
  cooler: '#a855f7',
  value: '#22c55e',
  study: '#60a5fa',
  'great play': '#10b981',
};

export const PRESET_TAGS = ['mistake', 'bluff', 'cooler', 'value', 'study', 'great play'];

export function getTagColor(tag: string): string {
  return TAG_COLORS[tag.toLowerCase()] || '#6b7280';
}
