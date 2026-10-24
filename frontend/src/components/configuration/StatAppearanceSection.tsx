import { useState } from 'react';
import { Switch } from '@/components/ui/switch';
import type { StatAppearance } from '@/lib/config/types';
import { NumberField } from './NumberField';
import OptionRow from './OptionRow';
import SectionHeader from './SectionHeader';
import { ConfigError, ConfigLoading } from './ConfigState';
import { useConfigSection } from './useConfigSection';

type NumKey = 'one_decimal_below' | 'show_sample_below' | 'dim_below' | 'vs_user_substitute_above';
type BoolKey = 'show_99_for_100' | 'leading_zero' | 'shorten_amounts';

const NUMBERS: { key: NumKey; label: string; help: string; min: number; max: number; integer: boolean }[] = [
  { key: 'one_decimal_below', label: 'Show one decimal below', help: 'Percentages closer to zero than this show one decimal place (7.5), the rest are whole numbers.', min: 0, max: 100, integer: false },
  { key: 'show_sample_below', label: 'Show the sample below', help: 'A small grey sample number is shown after a value whose sample is smaller than this.', min: 1, max: 1_000_000, integer: true },
  { key: 'dim_below', label: 'Dim values below a sample of', help: 'Values with fewer observations than this are drawn dimmed.', min: 1, max: 1_000_000, integer: true },
  { key: 'vs_user_substitute_above', label: 'Use the vs-player value above a sample of', help: 'In player-specific views, show the value against that player once the sample is larger than this. 0 turns it off.', min: 0, max: 1_000_000, integer: true },
];

const SWITCHES: { key: BoolKey; label: string; help: string }[] = [
  { key: 'show_99_for_100', label: 'Show 99 instead of 100', help: 'An exact 100% prints as 99 so the column keeps two digits.' },
  { key: 'leading_zero', label: 'Leading zero for single digits', help: 'Whole percentages below 10 print as 05.' },
  { key: 'shorten_amounts', label: 'Shorten large numbers', help: 'Counts and amounts print as 1.2k or 3m instead of in full.' },
];

export default function StatAppearanceSection() {
  const { env, isError, error, update, reset } = useConfigSection<StatAppearance>('stat_appearance');
  const [errors, setErrors] = useState<Partial<Record<NumKey, string | null>>>({});
  if (isError) return <ConfigError error={error} />;
  if (!env) return <ConfigLoading />;
  const { value, default: def } = env;
  const set = (patch: Partial<StatAppearance>) => update((cur) => ({ ...cur, ...patch }));

  return (
    <div>
      <SectionHeader
        title="Stat Appearance"
        caption="How numbers look on the Statistics screen and in stat popups."
        onReset={reset}
        resetDescription="Number formatting and sample rules go back to their defaults."
      />
      <div>
        {NUMBERS.map((n) => (
          <OptionRow key={n.key} id={`sa-${n.key}`} label={n.label} help={n.help} changed={value[n.key] !== def[n.key]} error={errors[n.key]}>
            <NumberField
              id={`sa-${n.key}`}
              value={value[n.key]}
              spec={{ min: n.min, max: n.max, integer: n.integer }}
              onCommit={(v) => set({ [n.key]: v })}
              onError={(m) => setErrors((prev) => (prev[n.key] === m ? prev : { ...prev, [n.key]: m }))}
            />
          </OptionRow>
        ))}
        {SWITCHES.map((s) => (
          <OptionRow key={s.key} id={`sa-${s.key}`} label={s.label} help={s.help} changed={value[s.key] !== def[s.key]}>
            <Switch id={`sa-${s.key}`} checked={value[s.key]} onCheckedChange={(v) => set({ [s.key]: v })} />
          </OptionRow>
        ))}
      </div>
    </div>
  );
}
