import { useState, useRef, useEffect } from 'react';
import { getTagColor, PRESET_TAGS } from './tagColors';

export default function TagPicker({
  currentTags,
  onAdd,
  onRemove,
}: {
  currentTags: string[];
  onAdd: (tag: string) => void;
  onRemove: (tag: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [customTag, setCustomTag] = useState('');
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  const toggleTag = (tag: string) => {
    if (currentTags.includes(tag)) {
      onRemove(tag);
    } else {
      onAdd(tag);
    }
  };

  const handleCustomSubmit = () => {
    const t = customTag.trim().toLowerCase();
    if (t && !currentTags.includes(t)) {
      onAdd(t);
    }
    setCustomTag('');
  };

  return (
    <div className="relative inline-block" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="text-[11px] text-text-muted hover:text-primary border border-border rounded px-1.5 py-0.5 hover:border-primary transition-colors"
      >
        + Add tag
      </button>
      {open && (
        <div className="absolute z-50 top-full left-0 mt-1 bg-surface border border-border rounded-lg shadow-lg p-2 w-48">
          <div className="flex flex-wrap gap-1 mb-2">
            {PRESET_TAGS.map((tag) => {
              const active = currentTags.includes(tag);
              const color = getTagColor(tag);
              return (
                <button
                  key={tag}
                  onClick={() => toggleTag(tag)}
                  className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[11px] border transition-colors ${
                    active
                      ? 'border-primary bg-primary/10 text-text'
                      : 'border-border hover:border-text-muted text-text-muted'
                  }`}
                >
                  <span
                    className="w-1.5 h-1.5 rounded-full"
                    style={{ backgroundColor: color }}
                  />
                  {tag}
                </button>
              );
            })}
          </div>
          <div className="flex gap-1">
            <input
              type="text"
              value={customTag}
              onChange={(e) => setCustomTag(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleCustomSubmit(); }}
              placeholder="Custom tag..."
              className="flex-1 bg-background border border-border rounded px-1.5 py-0.5 text-[11px] text-text placeholder:text-text-muted outline-none focus:border-primary"
            />
          </div>
        </div>
      )}
    </div>
  );
}
