import { useEffect, useState } from 'react';
import { Input } from '@/components/ui/input';
import { parseNumberField, parseRangePair, type NumberSpec } from '@/lib/config/logic';
import { useDebouncedCommit } from './useDebouncedCommit';

/** Number input that saves ~400 ms after the last valid keystroke (and on blur). Shows its error via `onError`. */
export function NumberField({ id, value, spec, onCommit, onError, label, className = 'w-24' }: {
  id?: string;
  value: number;
  spec: NumberSpec;
  onCommit: (v: number) => void;
  onError?: (message: string | null) => void;
  label?: string;
  className?: string;
}) {
  const [text, setText] = useState(String(value));
  const [lastValue, setLastValue] = useState(value);
  if (value !== lastValue) {
    // The stored value changed from outside (reset, other tab): follow it
    setLastValue(value);
    const parsed = parseNumberField(text, spec);
    if (!('value' in parsed) || parsed.value !== value) setText(String(value));
  }
  const { schedule, flush, cancel } = useDebouncedCommit(onCommit);
  const parsed = parseNumberField(text, spec);
  const error = 'error' in parsed ? parsed.error : null;
  useEffect(() => onError?.(error), [error, onError]);

  return (
    <Input
      id={id}
      aria-label={label}
      type="text"
      inputMode={spec.integer === false ? 'decimal' : 'numeric'}
      value={text}
      aria-invalid={error !== null}
      className={className}
      onChange={(e) => {
        const next = e.target.value;
        setText(next);
        const p = parseNumberField(next, spec);
        if ('value' in p && p.value !== value) schedule(p.value);
        else cancel();
      }}
      onBlur={() => {
        if (error) {
          cancel();
          setText(String(value));
        } else flush();
      }}
    />
  );
}

/** Two number inputs (from / to) validated together. */
export function RangeField({ idPrefix, label, value, spec, onCommit, onError }: {
  idPrefix: string;
  label: string;
  value: [number, number];
  spec: NumberSpec;
  onCommit: (v: [number, number]) => void;
  onError?: (message: string | null) => void;
}) {
  const [texts, setTexts] = useState<[string, string]>([String(value[0]), String(value[1])]);
  const [last, setLast] = useState(value);
  if (value[0] !== last[0] || value[1] !== last[1]) {
    setLast(value);
    const p = parseRangePair(texts[0], texts[1], spec);
    if (!('value' in p) || p.value[0] !== value[0] || p.value[1] !== value[1]) setTexts([String(value[0]), String(value[1])]);
  }
  const { schedule, flush, cancel } = useDebouncedCommit(onCommit);
  const parsed = parseRangePair(texts[0], texts[1], spec);
  const error = 'error' in parsed ? parsed.error : null;
  useEffect(() => onError?.(error), [error, onError]);

  const change = (i: 0 | 1, v: string) => {
    const next: [string, string] = i === 0 ? [v, texts[1]] : [texts[0], v];
    setTexts(next);
    const p = parseRangePair(next[0], next[1], spec);
    if ('value' in p && (p.value[0] !== value[0] || p.value[1] !== value[1])) schedule(p.value);
    else cancel();
  };
  const blur = () => {
    if (error) {
      cancel();
      setTexts([String(value[0]), String(value[1])]);
    } else flush();
  };

  return (
    <div className="flex items-center gap-2">
      <Input id={`${idPrefix}-from`} aria-label={`${label} from`} inputMode="numeric" value={texts[0]} aria-invalid={error !== null} className="w-20" onChange={(e) => change(0, e.target.value)} onBlur={blur} />
      <span aria-hidden className="text-muted-foreground">–</span>
      <Input id={`${idPrefix}-to`} aria-label={`${label} to`} inputMode="numeric" value={texts[1]} aria-invalid={error !== null} className="w-20" onChange={(e) => change(1, e.target.value)} onBlur={blur} />
    </div>
  );
}
