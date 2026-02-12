import type { TagCount } from '@/lib/api';
import { formatStakes } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover';
import { DatePicker } from '@/components/ui/date-picker';

interface FilterState {
  position: string[];
  stakes: string[];
  result: string;
  tags: string[];
  date: string;
  dateFrom: string;
  dateTo: string;
  search: string;
  statFlags: string[];
  quickFilters: string[];
}

// ── Quick filter definitions ─────────────────────────────────────────

interface QuickFilterDef {
  key: string;
  label: string;
  category: 'preflop' | 'postflop' | 'general';
  /** stat_flag values to send to backend (prefix ! for negation) */
  flags: string[];
}

const QUICK_FILTERS: QuickFilterDef[] = [
  // Preflop
  { key: 'vpip', label: 'Did VPIP', category: 'preflop', flags: ['vpip'] },
  { key: 'rfi', label: 'Raise 1st', category: 'preflop', flags: ['open_raise'] },
  { key: 'call_open', label: 'Call Open Raise', category: 'preflop', flags: ['call_open_raise'] },
  { key: '3bet', label: '3-Bet', category: 'preflop', flags: ['three_bet'] },
  { key: '4bet', label: '4-Bet', category: 'preflop', flags: ['four_bet'] },
  { key: 'squeeze', label: 'Squeeze', category: 'preflop', flags: ['squeeze'] },
  { key: 'steal', label: 'Steal', category: 'preflop', flags: ['steal_attempted'] },
  { key: 'limp', label: 'Limp', category: 'preflop', flags: ['limp'] },

  // Postflop
  { key: 'cbet_flop', label: 'Cbet Flop', category: 'postflop', flags: ['cbet_flop'] },
  { key: '2barrel', label: '2nd Barrel', category: 'postflop', flags: ['cbet_turn'] },
  { key: '3barrel', label: '3rd Barrel', category: 'postflop', flags: ['cbet_river'] },
  { key: 'missed_cbet', label: 'Missed Cbet Flop', category: 'postflop', flags: ['missed_cbet_flop'] },
  { key: 'fold_to_cbet', label: 'Fold to Cbet Flop', category: 'postflop', flags: ['fold_to_cbet_flop'] },
  { key: 'donk_flop', label: 'Donk Bet Flop', category: 'postflop', flags: ['donk_bet_flop'] },

  // General
  { key: 'saw_flop', label: 'Saw Flop', category: 'general', flags: ['saw_flop'] },
  { key: 'showdown', label: 'Went to Showdown', category: 'general', flags: ['went_to_showdown'] },
  { key: 'fold_before_sd', label: 'Fold Before SD', category: 'general', flags: ['saw_flop', '!went_to_showdown'] },
  { key: 'won_sd', label: 'Won at Showdown', category: 'general', flags: ['won_at_showdown'] },
];

const QUICK_FILTERS_MAP = Object.fromEntries(QUICK_FILTERS.map((q) => [q.key, q]));

// ── Shared components ────────────────────────────────────────────────

function FilterDropdown({
  label,
  children,
  active,
  wide,
}: {
  label: string;
  children: React.ReactNode;
  active: boolean;
  wide?: boolean;
}) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant={active ? 'secondary' : 'outline'}
          size="sm"
          className={`h-7 text-xs ${active ? 'border-primary text-primary bg-primary/10' : ''}`}
        >
          {label} &#9662;
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className={`${wide ? 'w-auto min-w-[420px]' : 'w-auto min-w-[160px]'} p-2`}>
        {children}
      </PopoverContent>
    </Popover>
  );
}

function CheckboxOption({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (c: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 py-0.5 cursor-pointer text-[12px] text-text hover:text-primary">
      <Checkbox
        checked={checked}
        onCheckedChange={(c) => onChange(c === true)}
      />
      {label}
    </label>
  );
}

const POSITIONS = ['EP', 'MP', 'CO', 'BTN', 'SB', 'BB'];
const RESULTS = [
  { value: '', label: 'All' },
  { value: 'won', label: 'Won (>0)' },
  { value: 'lost', label: 'Lost (<0)' },
  { value: 'big_win', label: 'Big Win (>10bb)' },
  { value: 'big_loss', label: 'Big Loss (<-10bb)' },
  { value: 'breakeven', label: 'Break Even' },
];
const DATE_PRESETS = [
  { value: '', label: 'All Time' },
  { value: 'today', label: 'Today' },
  { value: 'week', label: 'This Week' },
  { value: 'month', label: 'This Month' },
  { value: 'custom', label: 'Custom Range' },
];

export default function HandFilters({
  filters,
  onChange,
  distinctStakes,
  allTags,
  lockedStatFlags,
}: {
  filters: FilterState;
  onChange: (f: FilterState) => void;
  distinctStakes: string[];
  allTags: TagCount[];
  lockedStatFlags?: string[];
}) {
  const hasFilters =
    filters.position.length > 0 ||
    filters.stakes.length > 0 ||
    filters.result !== '' ||
    filters.tags.length > 0 ||
    filters.date !== '' ||
    filters.search !== '' ||
    filters.statFlags.length > 0 ||
    filters.quickFilters.length > 0;

  const clearAll = () =>
    onChange({
      position: [],
      stakes: [],
      result: '',
      tags: [],
      date: '',
      dateFrom: '',
      dateTo: '',
      search: '',
      statFlags: [],
      quickFilters: [],
    });

  const toggleQuickFilter = (key: string, checked: boolean) => {
    const next = checked
      ? [...filters.quickFilters, key]
      : filters.quickFilters.filter((k) => k !== key);
    onChange({ ...filters, quickFilters: next });
  };

  return (
    <Card className="gap-0 py-0">
      <CardContent className="px-3 py-2 flex items-center gap-2 flex-wrap">
        {/* Quick Filters */}
        <FilterDropdown label="Quick Filters" active={filters.quickFilters.length > 0} wide>
          <div className="flex gap-5">
            <div className="min-w-[120px]">
              <div className="text-[11px] uppercase tracking-wide text-text-muted mb-1.5 font-medium">Preflop</div>
              {QUICK_FILTERS.filter((q) => q.category === 'preflop').map((q) => (
                <CheckboxOption
                  key={q.key}
                  label={q.label}
                  checked={filters.quickFilters.includes(q.key)}
                  onChange={(c) => toggleQuickFilter(q.key, c)}
                />
              ))}
            </div>
            <div className="min-w-[130px]">
              <div className="text-[11px] uppercase tracking-wide text-text-muted mb-1.5 font-medium">Postflop</div>
              {QUICK_FILTERS.filter((q) => q.category === 'postflop').map((q) => (
                <CheckboxOption
                  key={q.key}
                  label={q.label}
                  checked={filters.quickFilters.includes(q.key)}
                  onChange={(c) => toggleQuickFilter(q.key, c)}
                />
              ))}
            </div>
            <div className="min-w-[120px]">
              <div className="text-[11px] uppercase tracking-wide text-text-muted mb-1.5 font-medium">General</div>
              {QUICK_FILTERS.filter((q) => q.category === 'general').map((q) => (
                <CheckboxOption
                  key={q.key}
                  label={q.label}
                  checked={filters.quickFilters.includes(q.key)}
                  onChange={(c) => toggleQuickFilter(q.key, c)}
                />
              ))}
            </div>
          </div>
        </FilterDropdown>

        {/* Stakes */}
        <FilterDropdown label="Stakes" active={filters.stakes.length > 0}>
          {distinctStakes.map((s) => (
            <CheckboxOption
              key={s}
              label={formatStakes(s)}
              checked={filters.stakes.includes(s)}
              onChange={(c) => {
                const next = c ? [...filters.stakes, s] : filters.stakes.filter((x) => x !== s);
                onChange({ ...filters, stakes: next });
              }}
            />
          ))}
          {distinctStakes.length === 0 && (
            <span className="text-[11px] text-text-muted">No stakes found</span>
          )}
        </FilterDropdown>

        {/* Position */}
        <FilterDropdown label="Position" active={filters.position.length > 0}>
          {POSITIONS.map((p) => (
            <CheckboxOption
              key={p}
              label={p}
              checked={filters.position.includes(p)}
              onChange={(c) => {
                const next = c ? [...filters.position, p] : filters.position.filter((x) => x !== p);
                onChange({ ...filters, position: next });
              }}
            />
          ))}
        </FilterDropdown>

        {/* Result */}
        <FilterDropdown label="Result" active={filters.result !== ''}>
          <RadioGroup
            value={filters.result}
            onValueChange={(v) => onChange({ ...filters, result: v })}
            className="gap-1"
          >
            {RESULTS.map((r) => (
              <label key={r.value} className="flex items-center gap-2 py-0.5 cursor-pointer text-[12px] text-text hover:text-primary">
                <RadioGroupItem value={r.value} />
                {r.label}
              </label>
            ))}
          </RadioGroup>
        </FilterDropdown>

        {/* Tags */}
        <FilterDropdown label="Tags" active={filters.tags.length > 0}>
          <CheckboxOption
            label="Untagged"
            checked={filters.tags.includes('untagged')}
            onChange={(c) => {
              const next = c
                ? [...filters.tags, 'untagged']
                : filters.tags.filter((x) => x !== 'untagged');
              onChange({ ...filters, tags: next });
            }}
          />
          {allTags.map((t) => (
            <CheckboxOption
              key={t.tag}
              label={`${t.tag} (${t.count})`}
              checked={filters.tags.includes(t.tag)}
              onChange={(c) => {
                const next = c
                  ? [...filters.tags, t.tag]
                  : filters.tags.filter((x) => x !== t.tag);
                onChange({ ...filters, tags: next });
              }}
            />
          ))}
        </FilterDropdown>

        {/* Date */}
        <FilterDropdown label="Date" active={filters.date !== ''}>
          <RadioGroup
            value={filters.date}
            onValueChange={(v) => onChange({ ...filters, date: v })}
            className="gap-1"
          >
            {DATE_PRESETS.map((d) => (
              <label key={d.value} className="flex items-center gap-2 py-0.5 cursor-pointer text-[12px] text-text hover:text-primary">
                <RadioGroupItem value={d.value} />
                {d.label}
              </label>
            ))}
          </RadioGroup>
          {filters.date === 'custom' && (
            <div className="flex flex-col gap-1.5 mt-2 pt-2 border-t border-border">
              <DatePicker
                value={filters.dateFrom}
                onChange={(v) => onChange({ ...filters, dateFrom: v })}
                placeholder="From"
                className="h-7 text-xs w-full"
              />
              <DatePicker
                value={filters.dateTo}
                onChange={(v) => onChange({ ...filters, dateTo: v })}
                placeholder="To"
                className="h-7 text-xs w-full"
              />
            </div>
          )}
        </FilterDropdown>

        {/* Search */}
        <Input
          type="text"
          value={filters.search}
          onChange={(e) => onChange({ ...filters, search: e.target.value })}
          placeholder="Search hand ID..."
          className="h-7 text-xs w-40"
        />

        {/* Locked stat flag badges (non-removable) */}
        {lockedStatFlags?.map((flag) => (
          <span
            key={`locked-${flag}`}
            className="inline-flex items-center gap-1 h-7 px-2 text-xs bg-primary/10 text-primary border border-primary/30 rounded"
          >
            {flag.replace(/_/g, ' ')}
          </span>
        ))}

        {/* Stat flag badges */}
        {filters.statFlags.map((flag) => (
          <span
            key={flag}
            className="inline-flex items-center gap-1 h-7 px-2 text-xs bg-primary/10 text-primary border border-primary/30 rounded"
          >
            {flag.replace(/_/g, ' ')}
            <button
              className="ml-0.5 text-primary/60 hover:text-primary"
              onClick={() => onChange({ ...filters, statFlags: filters.statFlags.filter((f) => f !== flag) })}
            >
              &times;
            </button>
          </span>
        ))}

        {/* Quick filter badges */}
        {filters.quickFilters.map((key) => {
          const def = QUICK_FILTERS_MAP[key];
          if (!def) return null;
          return (
            <span
              key={`qf-${key}`}
              className="inline-flex items-center gap-1 h-7 px-2 text-xs bg-primary/10 text-primary border border-primary/30 rounded"
            >
              {def.label}
              <button
                className="ml-0.5 text-primary/60 hover:text-primary"
                onClick={() => onChange({ ...filters, quickFilters: filters.quickFilters.filter((k) => k !== key) })}
              >
                &times;
              </button>
            </span>
          );
        })}

        {hasFilters && (
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs text-text-muted hover:text-red"
            onClick={clearAll}
          >
            Clear all
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

export { QUICK_FILTERS, QUICK_FILTERS_MAP };
export type { FilterState, QuickFilterDef };
