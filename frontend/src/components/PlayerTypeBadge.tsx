const TYPE_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  NIT: { bg: 'bg-zinc-700/60', text: 'text-zinc-300', label: 'NIT' },
  TAG: { bg: 'bg-blue-600/30', text: 'text-blue-400', label: 'TAG' },
  LAG: { bg: 'bg-orange-600/30', text: 'text-orange-400', label: 'LAG' },
  REC: { bg: 'bg-emerald-600/30', text: 'text-emerald-400', label: 'REC' },
  MAN: { bg: 'bg-red-600/30', text: 'text-red-400', label: 'MAN' },
  UNK: { bg: 'bg-zinc-800/40', text: 'text-zinc-500', label: 'UNK' },
};

export default function PlayerTypeBadge({
  type,
  className = '',
}: {
  type: string;
  className?: string;
}) {
  const style = TYPE_STYLES[type] ?? TYPE_STYLES.UNK;
  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-bold tracking-wide ${style.bg} ${style.text} ${className}`}
    >
      {style.label}
    </span>
  );
}
