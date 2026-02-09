export type DatePreset = 'today' | 'week' | 'month' | 'all';

export function getPresetDates(preset: DatePreset): { date_from?: string; date_to?: string } {
  if (preset === 'all') return {};
  const now = new Date();
  if (preset === 'today') {
    return { date_from: now.toISOString().slice(0, 10) };
  }
  if (preset === 'week') {
    const day = now.getDay();
    const diff = day === 0 ? 6 : day - 1; // Monday = 0
    const monday = new Date(now);
    monday.setDate(now.getDate() - diff);
    return { date_from: monday.toISOString().slice(0, 10) };
  }
  // month
  const first = new Date(now.getFullYear(), now.getMonth(), 1);
  return { date_from: first.toISOString().slice(0, 10) };
}
