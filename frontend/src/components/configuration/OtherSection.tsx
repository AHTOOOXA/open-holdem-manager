import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { appSettingsQueryKey, getAppSettings, patchAppSettings, type AppSettings } from '@/lib/app-settings';
import { DAY_START_RANGE, MAX_BREAK_RANGE, parseIntField } from './other-fields';

function Field({ id, label, hint, value, error, onChange }: {
  id: string;
  label: string;
  hint: string;
  value: string;
  error: string | null;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium">{label}</label>
      <Input
        id={id}
        type="number"
        inputMode="numeric"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={error !== null}
        aria-describedby={`${id}-hint`}
        className="w-32"
      />
      <p id={`${id}-hint`} className={error ? 'text-sm text-money-neg' : 'text-sm text-muted-foreground'} role={error ? 'alert' : undefined}>
        {error ?? hint}
      </p>
    </div>
  );
}

function OtherForm({ settings }: { settings: AppSettings }) {
  const queryClient = useQueryClient();
  const [breakText, setBreakText] = useState(String(settings.session_max_break_minutes));
  const [dayText, setDayText] = useState(String(settings.day_start_hour));

  const breakParsed = parseIntField(breakText, MAX_BREAK_RANGE);
  const dayParsed = parseIntField(dayText, DAY_START_RANGE);
  const breakError = 'error' in breakParsed ? breakParsed.error : null;
  const dayError = 'error' in dayParsed ? dayParsed.error : null;
  const valid = !breakError && !dayError;
  const dirty = valid
    && ('value' in breakParsed && breakParsed.value !== settings.session_max_break_minutes
      || 'value' in dayParsed && dayParsed.value !== settings.day_start_hour);

  const save = useMutation({
    mutationFn: (patch: Partial<AppSettings>) => patchAppSettings(patch),
    onSuccess: (next) => {
      queryClient.setQueryData(appSettingsQueryKey, next);
      // Session boundaries (and date presets) depend on these
      void queryClient.invalidateQueries({ queryKey: ['sessions'] });
    },
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!dirty || !('value' in breakParsed) || !('value' in dayParsed)) return;
    save.mutate({ session_max_break_minutes: breakParsed.value, day_start_hour: dayParsed.value });
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-5">
      <Field
        id="max-break"
        label="Max break between sessions (minutes)"
        hint="A hand that starts less than this after the current session's end (last hand start plus 3 minutes) stays in that session."
        value={breakText}
        error={breakError}
        onChange={setBreakText}
      />
      <Field
        id="day-start"
        label="Day starts at (hour)"
        hint="0-23. Used by the Sessions date presets (Today, This Week, ...); Reports presets do not use it yet."
        value={dayText}
        error={dayError}
        onChange={setDayText}
      />
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={!dirty || save.isPending}>Save</Button>
        {save.isError && <span role="alert" className="text-sm text-money-neg">Saving failed. {save.error.message}</span>}
        {save.isSuccess && !dirty && <span role="status" className="text-sm text-muted-foreground">Saved</span>}
      </div>
    </form>
  );
}

export default function OtherSection() {
  const { data, isError, error } = useQuery({ queryKey: appSettingsQueryKey, queryFn: getAppSettings });
  if (isError) return <p role="alert" className="text-sm text-money-neg">Couldn't load settings. {error.message}</p>;
  if (!data) return <p className="text-sm text-muted-foreground">Loading…</p>;
  return <OtherForm settings={data} />;
}
