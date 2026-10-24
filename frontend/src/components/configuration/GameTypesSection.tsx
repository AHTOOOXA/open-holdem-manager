import { useState } from 'react';
import type { GameTypesConfig, RegRule } from '@/lib/config/types';
import { NumberField, RangeField } from './NumberField';
import OptionRow from './OptionRow';
import SectionHeader from './SectionHeader';
import { ConfigError, ConfigLoading } from './ConfigState';
import { useConfigSection } from './useConfigSection';

type RangeKey = 'vpip' | 'pfr' | 'vpip_minus_pfr' | 'limp';
const RANGES: { key: RangeKey; label: string; help: string }[] = [
  { key: 'vpip', label: 'VPIP', help: 'A player is a regular when their VPIP is inside this range (percent, both ends included).' },
  { key: 'pfr', label: 'PFR', help: 'PFR must be inside this range.' },
  { key: 'vpip_minus_pfr', label: 'VPIP − PFR', help: 'The gap between VPIP and PFR must be inside this range.' },
  { key: 'limp', label: 'Limp', help: 'The limp percentage must be inside this range.' },
];

const same = (a: [number, number], b: [number, number]) => a[0] === b[0] && a[1] === b[1];

export default function GameTypesSection() {
  const { env, isError, error, update, reset } = useConfigSection<GameTypesConfig>('game_types');
  const [errors, setErrors] = useState<Record<string, string | null>>({});
  if (isError) return <ConfigError error={error} />;
  if (!env) return <ConfigLoading />;
  const rule = env.value.reg_rule;
  const def = env.default.reg_rule;
  const set = (patch: Partial<RegRule>) => update((cur) => ({ ...cur, reg_rule: { ...cur.reg_rule, ...patch } }));
  const err = (k: string) => (m: string | null) => setErrors((p) => (p[k] === m ? p : { ...p, [k]: m }));

  return (
    <div>
      <SectionHeader
        title="Game Types"
        caption="Rebuild statistics after you change the rule."
        onReset={reset}
        resetDescription="The 'Who is regular?' rule goes back to its defaults. Rebuild statistics afterwards."
      />
      <h3 className="mb-1 text-sm font-semibold">Who is regular?</h3>
      <p className="mb-2 text-sm text-muted-foreground">
        A player with enough hands is a regular when every range below holds. Everyone else is a fish.
      </p>
      <OptionRow id="reg-min-hands" label="Minimum hands" help="Players with fewer hands than this are always fish." changed={rule.min_hands !== def.min_hands} error={errors.min_hands}>
        <NumberField id="reg-min-hands" value={rule.min_hands} spec={{ min: 0, max: 10_000_000 }} onCommit={(v) => set({ min_hands: v })} onError={err('min_hands')} />
      </OptionRow>
      {RANGES.map((r) => (
        <OptionRow key={r.key} id={`reg-${r.key}-from`} label={r.label} help={r.help} changed={!same(rule[r.key], def[r.key])} error={errors[r.key]}>
          <RangeField idPrefix={`reg-${r.key}`} label={r.label} value={rule[r.key]} spec={{ min: 0, max: 100 }} onCommit={(v) => set({ [r.key]: v })} onError={err(r.key)} />
        </OptionRow>
      ))}
      <p className="py-2 text-label font-medium uppercase tracking-wide text-subtle-foreground">or</p>
      <OptionRow id="reg-auto" label="Always a regular from (hands)" help="At or above this many hands a player is a regular whatever their stats say. 0 turns it off." changed={rule.auto_reg_hands !== def.auto_reg_hands} error={errors.auto_reg_hands}>
        <NumberField id="reg-auto" value={rule.auto_reg_hands} spec={{ min: 0, max: 100_000_000 }} onCommit={(v) => set({ auto_reg_hands: v })} onError={err('auto_reg_hands')} className="w-28" />
      </OptionRow>
    </div>
  );
}
