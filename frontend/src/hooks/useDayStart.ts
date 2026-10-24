import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { APP_SETTINGS_DEFAULTS, appSettingsQueryKey, getAppSettings } from '@/lib/app-settings';
import { formatLocalDate } from '@/lib/date';
import { setAppDayStartHour, shiftForDayStart } from '@/lib/reports/steps';

/** The "Day starts at (hour)" setting; also syncs the preset default used by `sessionPresets`. */
export function useDayStartHour(): number {
  const { data } = useQuery({ queryKey: appSettingsQueryKey, queryFn: getAppSettings, staleTime: 60_000 });
  const hour = data?.day_start_hour ?? APP_SETTINGS_DEFAULTS.day_start_hour;
  // During render on purpose: children computing presets in this same render must see the new hour
  setAppDayStartHour(hour);
  return hour;
}

/** Calendar day under the day-start rule ("2026-10-24"). */
export function dayKey(now: Date, dayStartHour: number): string {
  return formatLocalDate(shiftForDayStart(now, dayStartHour));
}

/** The current day key (+ the day-start hour); updates on focus / visibility and every minute. */
export function useDayKey(): string {
  const hour = useDayStartHour();
  const [key, setKey] = useState(() => dayKey(new Date(), hour));
  useEffect(() => {
    const tick = () => setKey(dayKey(new Date(), hour));
    tick();
    const id = window.setInterval(tick, 60_000);
    window.addEventListener('focus', tick);
    document.addEventListener('visibilitychange', tick);
    return () => {
      window.clearInterval(id);
      window.removeEventListener('focus', tick);
      document.removeEventListener('visibilitychange', tick);
    };
  }, [hour]);
  return `${key}|${hour}`;
}
