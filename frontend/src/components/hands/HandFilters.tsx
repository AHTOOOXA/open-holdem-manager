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
}

function FilterDropdown({
  label,
  children,
  active,
}: {
  label: string;
  children: React.ReactNode;
  active: boolean;
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
      <PopoverContent align="start" className="w-auto min-w-[160px] p-2">
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
}: {
  filters: FilterState;
  onChange: (f: FilterState) => void;
  distinctStakes: string[];
  allTags: TagCount[];
}) {
  const hasFilters =
    filters.position.length > 0 ||
    filters.stakes.length > 0 ||
    filters.result !== '' ||
    filters.tags.length > 0 ||
    filters.date !== '' ||
    filters.search !== '' ||
    filters.statFlags.length > 0;

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
    });

  return (
    <Card className="gap-0 py-0">
      <CardContent className="px-3 py-2 flex items-center gap-2 flex-wrap">
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

export type { FilterState };
