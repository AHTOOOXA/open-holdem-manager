/** Workspace colours are stored data (the backend keeps the hex string), so they are exempt from the colour ratchet. */
export const PRESET_COLORS: { label: string; value: string | null }[] = [
  { label: 'Gray', value: null },
  { label: 'Blue', value: '#3b82f6' },
  { label: 'Green', value: '#22c55e' },
  { label: 'Purple', value: '#a855f7' },
  { label: 'Orange', value: '#f97316' },
  { label: 'Pink', value: '#ec4899' },
  { label: 'Red', value: '#ef4444' },
  { label: 'Yellow', value: '#eab308' },
  { label: 'Cyan', value: '#06b6d4' },
];
