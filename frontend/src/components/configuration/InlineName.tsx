import { useRef, useState, type Ref } from 'react';
import { Input } from '@/components/ui/input';
import { validName } from '@/lib/config/logic';

/**
 * Always-editable name: Enter saves, Escape reverts, blur saves, an empty name is rejected
 * (reverts and reports). `inputRef` lets a row's "edit" action focus it.
 */
export default function InlineName({ value, label, onSave, onReject, inputRef }: {
  value: string;
  label: string;
  onSave: (name: string) => void;
  onReject?: () => void;
  inputRef?: Ref<HTMLInputElement>;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  const skipBlur = useRef(false);
  const text = draft ?? value;

  const commit = () => {
    if (draft === null) return;
    const name = validName(draft);
    setDraft(null);
    if (name === null) onReject?.();
    else if (name !== value) onSave(name);
  };

  return (
    <Input
      ref={inputRef}
      aria-label={label}
      value={text}
      maxLength={60}
      aria-invalid={draft !== null && validName(draft) === null}
      className="h-control border-transparent bg-transparent hover:border-input focus-visible:border-ring"
      onChange={(e) => setDraft(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === 'Enter') {
          skipBlur.current = true;
          commit();
          e.currentTarget.blur();
        } else if (e.key === 'Escape') {
          skipBlur.current = true;
          setDraft(null);
          e.currentTarget.blur();
        }
      }}
      onBlur={() => {
        if (skipBlur.current) skipBlur.current = false;
        else commit();
      }}
    />
  );
}
