import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  APP_SETTINGS_DEFAULTS, appSettingsQueryKey, getAppSettings, patchAppSettings, resetAppSettings, type AppSettings,
} from '@/lib/app-settings';
import { DAY_START_RANGE, MAX_BREAK_RANGE } from './other-fields';
import { Switch } from '@/components/ui/switch';
import { ConfigError, ConfigLoading } from './ConfigState';
import { NumberField } from './NumberField';
import OptionRow from './OptionRow';
import SectionHeader from './SectionHeader';

export default function OtherSection() {
  const queryClient = useQueryClient();
  const { data, isError, error } = useQuery({ queryKey: appSettingsQueryKey, queryFn: getAppSettings });
  const [errors, setErrors] = useState<Record<string, string | null>>({});

  const afterSave = (next: AppSettings) => {
    queryClient.setQueryData(appSettingsQueryKey, next);
    // Session boundaries and date presets (Sessions, Statistics, Reports) depend on these
    void queryClient.invalidateQueries();
  };
  const save = useMutation({
    mutationFn: (patch: Partial<AppSettings>) => patchAppSettings(patch),
    onSuccess: afterSave,
    onError: (e: Error) => {
      toast.error('Saving failed', { description: e.message });
      void queryClient.invalidateQueries({ queryKey: appSettingsQueryKey });
    },
  });
  const reset = useMutation({ mutationFn: resetAppSettings, onSuccess: afterSave });

  if (isError) return <ConfigError error={error} />;
  if (!data) return <ConfigLoading />;
  const err = (k: string) => (m: string | null) => setErrors((p) => (p[k] === m ? p : { ...p, [k]: m }));

  return (
    <div>
      <SectionHeader
        title="Other"
        onReset={() => reset.mutateAsync()}
        resetDescription="Max break and day start go back to their defaults. The date format is kept."
      />
      <OptionRow
        id="max-break"
        label="Max break between sessions (minutes)"
        help="A hand that starts less than this after the current session's end (last hand start plus 3 minutes) stays in that session."
        changed={data.session_max_break_minutes !== APP_SETTINGS_DEFAULTS.session_max_break_minutes}
        error={errors.break}
      >
        <NumberField id="max-break" value={data.session_max_break_minutes} spec={MAX_BREAK_RANGE} onCommit={(v) => save.mutate({ session_max_break_minutes: v })} onError={err('break')} />
      </OptionRow>
      <OptionRow
        id="day-start"
        label="Day starts at (hour)"
        help="0-23. Before this hour it is still the previous day for the date presets (Today, This Week, ...) in Sessions, Statistics and Reports."
        changed={data.day_start_hour !== APP_SETTINGS_DEFAULTS.day_start_hour}
        error={errors.day}
      >
        <NumberField id="day-start" value={data.day_start_hour} spec={DAY_START_RANGE} onCommit={(v) => save.mutate({ day_start_hour: v })} onError={err('day')} />
      </OptionRow>
      <OptionRow
        id="numeric-date"
        label="Numeric date format"
        help="Sessions captions read 17-10-2026, 20:10 instead of October 17, Friday 20:10."
      >
        <Switch id="numeric-date" checked={data.numeric_date_format} onCheckedChange={(v) => save.mutate({ numeric_date_format: v })} />
      </OptionRow>
    </div>
  );
}
