/**
 * Notes tab of a profile dashboard: the player's notes (GET /api/players/{id} → notes), saved
 * ~600 ms after the last keystroke and on blur (PATCH /api/players/{id}/notes).
 */
import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Textarea } from '@/components/ui/textarea';
import { getPlayer, updatePlayerNotes, type PlayerHeader } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';

const SAVE_DELAY_MS = 600;

export default function NotesTab({ playerId }: { playerId: number | null }) {
  const q = useQuery({
    queryKey: queryKeys.players.detail(playerId ?? -1),
    queryFn: () => getPlayer(playerId!),
    enabled: playerId != null,
  });
  if (playerId == null) return <p className="text-sm text-muted-foreground">No player selected.</p>;
  if (q.isPending) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (q.isError) return <p role="alert" className="text-sm text-muted-foreground">Could not load the notes. {q.error.message}</p>;
  return <NotesEditor key={playerId} playerId={playerId} initial={q.data.notes ?? ''} name={q.data.username} />;
}

type Status = 'idle' | 'dirty' | 'saving' | 'saved' | 'error';

function NotesEditor({ playerId, initial, name }: { playerId: number; initial: string; name: string }) {
  const qc = useQueryClient();
  const [text, setText] = useState(initial);
  const [status, setStatus] = useState<Status>('idle');
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const saved = useRef(initial);
  const latest = useRef(initial);

  const save = () => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    const value = latest.current;
    if (value === saved.current) return;
    setStatus('saving');
    updatePlayerNotes(playerId, { notes: value })
      .then(() => {
        saved.current = value;
        qc.setQueryData<PlayerHeader>(queryKeys.players.detail(playerId), (p) => (p ? { ...p, notes: value } : p));
        setStatus(latest.current === value ? 'saved' : 'dirty');
      })
      .catch(() => setStatus('error'));
  };

  // Leaving the tab / player with a pending edit still saves it
  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
    if (latest.current !== saved.current) {
      const value = latest.current;
      void updatePlayerNotes(playerId, { notes: value }).then(() => {
        qc.setQueryData<PlayerHeader>(queryKeys.players.detail(playerId), (p) => (p ? { ...p, notes: value } : p));
      });
    }
  }, [playerId, qc]);

  return (
    <div className="flex max-w-3xl flex-col gap-2">
      <Textarea
        aria-label={`Notes on ${name}`}
        placeholder={`Notes on ${name}`}
        value={text}
        rows={12}
        onChange={(e) => {
          setText(e.target.value);
          latest.current = e.target.value;
          setStatus('dirty');
          if (timer.current) clearTimeout(timer.current);
          timer.current = setTimeout(save, SAVE_DELAY_MS);
        }}
        onBlur={save}
        className="min-h-48 resize-y"
      />
      <span aria-live="polite" className="h-4 text-xs text-subtle-foreground">
        {status === 'saving' ? 'Saving…' : status === 'saved' ? 'Saved' : status === 'error' ? 'Could not save the notes' : ''}
      </span>
    </div>
  );
}
