interface Props {
  label: string;
  value: number | null;
  sample: number;
}

export default function ContextualRate({ label, value, sample }: Props) {
  if (value == null || sample === 0) return null;

  return (
    <div>
      <div className="text-[11px] text-muted-foreground mb-0.5">{label}</div>
      <div className="flex items-baseline gap-2">
        <span className="text-lg font-bold text-foreground">{value.toFixed(1)}%</span>
        <span className="text-[10px] text-muted-foreground">({sample})</span>
      </div>
    </div>
  );
}
