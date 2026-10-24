/** Validation of the Configuration › Other fields (pure; integer inputs with a range). */
export interface IntRange {
  min: number;
  max: number;
}

export const MAX_BREAK_RANGE: IntRange = { min: 1, max: 240 };
export const DAY_START_RANGE: IntRange = { min: 0, max: 23 };

/** The integer in `text`, or an error message for the inline hint. */
export function parseIntField(text: string, range: IntRange): { value: number } | { error: string } {
  const t = text.trim();
  const message = `Enter a whole number from ${range.min} to ${range.max}`;
  if (!/^\d+$/.test(t)) return { error: message };
  const value = Number(t);
  return value >= range.min && value <= range.max ? { value } : { error: message };
}
