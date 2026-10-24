/**
 * App-wide settings (not per workspace): GET/PATCH /api/app-settings.
 * Backend: backend/app/app_settings.py, stored in the `settings` key/value table.
 * Configuration › Other edits them (M5 adds the field, M6 the full section).
 */
export interface AppSettings {
  /** "Max break between sessions (minutes)": a hand starting less than this after the current
   *  session's end (last start + 180 s) joins it. Default 10, integer 1-240. */
  session_max_break_minutes: number;
  /** "Day starts at (hour)": date presets only, not session splitting. Default 0, 0-23. */
  day_start_hour: number;
  /** Sessions list captions as "17-10-2026, 20:10" instead of "October 17, Friday 20:10". */
  numeric_date_format: boolean;
}

export const APP_SETTINGS_DEFAULTS: AppSettings = {
  session_max_break_minutes: 10,
  day_start_hour: 0,
  numeric_date_format: false,
};

export const appSettingsQueryKey = ['app-settings'] as const;

export async function getAppSettings(): Promise<AppSettings> {
  const res = await fetch('/api/app-settings');
  if (!res.ok) throw new Error(`App settings failed: ${res.statusText}`);
  return res.json();
}

/** Partial update; returns the full settings. Invalid values are a 422. */
export async function patchAppSettings(patch: Partial<AppSettings>): Promise<AppSettings> {
  const res = await fetch('/api/app-settings', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  });
  if (!res.ok) throw new Error(`Saving settings failed: ${res.statusText}`);
  return res.json();
}

/** Configuration › Other "Reset to default": restores max break + day start (keeps numeric_date_format). */
export async function resetAppSettings(): Promise<AppSettings> {
  const res = await fetch('/api/app-settings', { method: 'DELETE' });
  if (!res.ok) throw new Error(`Resetting settings failed: ${res.statusText}`);
  return res.json();
}
