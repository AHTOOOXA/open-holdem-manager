import { useState } from 'react';
import { getTagColor, PRESET_TAGS } from './tagColors';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';

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
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="h-6 text-[11px] px-1.5">
          + Add tag
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-48 p-2" align="start">
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
        <Input
          value={customTag}
          onChange={(e) => setCustomTag(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') handleCustomSubmit(); }}
          placeholder="Custom tag..."
          className="h-6 text-[11px]"
        />
      </PopoverContent>
    </Popover>
  );
}
