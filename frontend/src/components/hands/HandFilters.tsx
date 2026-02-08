import { useState, useRef, useEffect } from 'react';
import type { TagCount } from '@/lib/api';

interface FilterState {
  position: string[];
  stakes: string[];
  result: string;
  tags: string[];
  date: string;
  dateFrom: string;
  dateTo: string;
  search: string;
}

function Dropdown({
  label,
  children,
  active,
}: {
  label: string;
  children: React.ReactNode;
  active: boolean;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className={`px-2.5 py-1 text-[12px] rounded border transition-colors ${
          active
            ? 'border-primary text-primary bg-primary/10'
            : 'border-border text-text-muted hover:border-text-muted'
        }`}
      >
        {label} &#9662;
      </button>
      {open && (
        <div className="absolute z-40 top-full left-0 mt-1 bg-surface border border-border rounded-lg shadow-lg p-2 min-w-[160px]">
          {children}
        </div>
      )}
    </div>
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
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="accent-primary"
      />
      {label}
    </label>
  );
}

function RadioOption({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: () => void;
}) {
  return (
    <label className="flex items-center gap-2 py-0.5 cursor-pointer text-[12px] text-text hover:text-primary">
      <input type="radio" checked={checked} onChange={onChange} className="accent-primary" />
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
    filters.search !== '';

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
    });

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {/* Stakes */}
      <Dropdown label="Stakes" active={filters.stakes.length > 0}>
        {distinctStakes.map((s) => (
          <CheckboxOption
            key={s}
            label={s}
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
      </Dropdown>

      {/* Position */}
      <Dropdown label="Position" active={filters.position.length > 0}>
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
      </Dropdown>

      {/* Result */}
      <Dropdown label="Result" active={filters.result !== ''}>
        {RESULTS.map((r) => (
          <RadioOption
            key={r.value}
            label={r.label}
            checked={filters.result === r.value}
            onChange={() => onChange({ ...filters, result: r.value })}
          />
        ))}
      </Dropdown>

      {/* Tags */}
      <Dropdown label="Tags" active={filters.tags.length > 0}>
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
      </Dropdown>

      {/* Date */}
      <Dropdown label="Date" active={filters.date !== ''}>
        {DATE_PRESETS.map((d) => (
          <RadioOption
            key={d.value}
            label={d.label}
            checked={filters.date === d.value}
            onChange={() => onChange({ ...filters, date: d.value })}
          />
        ))}
        {filters.date === 'custom' && (
          <div className="flex flex-col gap-1 mt-2 pt-2 border-t border-border">
            <input
              type="date"
              value={filters.dateFrom}
              onChange={(e) => onChange({ ...filters, dateFrom: e.target.value })}
              className="bg-background border border-border rounded px-1.5 py-0.5 text-[11px] text-text outline-none"
            />
            <input
              type="date"
              value={filters.dateTo}
              onChange={(e) => onChange({ ...filters, dateTo: e.target.value })}
              className="bg-background border border-border rounded px-1.5 py-0.5 text-[11px] text-text outline-none"
            />
          </div>
        )}
      </Dropdown>

      {/* Search */}
      <input
        type="text"
        value={filters.search}
        onChange={(e) => onChange({ ...filters, search: e.target.value })}
        placeholder="Search hand ID..."
        className="bg-background border border-border rounded px-2 py-1 text-[12px] text-text placeholder:text-text-muted outline-none focus:border-primary w-40"
      />

      {hasFilters && (
        <button
          onClick={clearAll}
          className="text-[11px] text-text-muted hover:text-red transition-colors"
        >
          Clear all
        </button>
      )}
    </div>
  );
}

export type { FilterState };
