import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

interface Props {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  destructive?: boolean;
  /** When set, the user must type this exact text before confirming */
  requireText?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function ConfirmDialog({ open, title, description, confirmLabel, destructive, requireText, onConfirm, onCancel }: Props) {
  const [typed, setTyped] = useState('');
  const blocked = requireText !== undefined && typed.trim() !== requireText;
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) { setTyped(''); onCancel(); } }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        {requireText !== undefined && (
          <label className="flex flex-col gap-1.5 text-sm text-muted-foreground">
            <span>
              Type <span className="font-medium text-foreground">{requireText}</span> to confirm
            </span>
            <Input
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              autoFocus
              autoComplete="off"
              onKeyDown={(e) => { if (e.key === 'Enter' && !blocked) { setTyped(''); onConfirm(); } }}
            />
          </label>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => { setTyped(''); onCancel(); }}>Cancel</Button>
          <Button variant={destructive ? 'destructive' : 'default'} disabled={blocked} onClick={() => { setTyped(''); onConfirm(); }}>{confirmLabel}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
