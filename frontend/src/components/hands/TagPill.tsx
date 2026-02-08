import { getTagColor } from './tagColors';

export default function TagPill({
  tag,
  onRemove,
}: {
  tag: string;
  onRemove?: () => void;
}) {
  const color = getTagColor(tag);
  return (
    <span
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[11px] border border-border bg-surface group"
    >
      <span
        className="w-1.5 h-1.5 rounded-full shrink-0"
        style={{ backgroundColor: color }}
      />
      <span className="text-text">{tag}</span>
      {onRemove && (
        <button
          onClick={(e) => { e.stopPropagation(); onRemove(); }}
          className="text-text-muted hover:text-red ml-0.5 hidden group-hover:inline leading-none"
        >
          &times;
        </button>
      )}
    </span>
  );
}
