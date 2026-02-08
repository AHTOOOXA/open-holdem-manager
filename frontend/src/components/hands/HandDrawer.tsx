import { useState, useEffect, useCallback } from 'react';
import type { HandDetail } from '@/lib/api';
import { getHandDetail, addTag, removeTag, updateNote } from '@/lib/api';
import { CardPair } from './CardDisplay';
import HandActionsDisplay from './HandActions';
import TagPill from './TagPill';
import TagPicker from './TagPicker';

function formatStakes(bbAmount: number): string {
  const nl = Math.round(bbAmount * 100);
  return `NL${nl}`;
}

export default function HandDrawer({
  handId,
  onClose,
  onPrev,
  onNext,
  onTagsChanged,
}: {
  handId: string;
  onClose: () => void;
  onPrev: () => void;
  onNext: () => void;
  onTagsChanged: () => void;
}) {
  const [hand, setHand] = useState<HandDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [showRaw, setShowRaw] = useState(false);
  const [note, setNote] = useState('');
  const [noteSaving, setNoteSaving] = useState(false);

  const loadHand = useCallback(async () => {
    setLoading(true);
    setShowRaw(false);
    try {
      const h = await getHandDetail(handId);
      setHand(h);
      setNote(h.note || '');
    } finally {
      setLoading(false);
    }
  }, [handId]);

  useEffect(() => {
    loadHand();
  }, [loadHand]);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === 'Escape') onClose();
      else if (e.key === 'j' || e.key === 'ArrowDown') { e.preventDefault(); onNext(); }
      else if (e.key === 'k' || e.key === 'ArrowUp') { e.preventDefault(); onPrev(); }
      else if (e.key === 'r') setShowRaw((s) => !s);
    }
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [onClose, onPrev, onNext]);

  const handleAddTag = async (tag: string) => {
    if (!hand) return;
    await addTag(hand.id, tag);
    setHand({ ...hand, tags: [...hand.tags, tag] });
    onTagsChanged();
  };

  const handleRemoveTag = async (tag: string) => {
    if (!hand) return;
    await removeTag(hand.id, tag);
    setHand({ ...hand, tags: hand.tags.filter((t) => t !== tag) });
    onTagsChanged();
  };

  const handleNoteSave = async () => {
    if (!hand) return;
    setNoteSaving(true);
    try {
      await updateNote(hand.id, note);
      setHand({ ...hand, note });
    } finally {
      setNoteSaving(false);
    }
  };

  const hero = hand?.players.find((p) => p.is_hero);
  const heroWonBb = hero?.won_bb ?? 0;

  return (
    <div className="fixed inset-y-0 right-0 w-[640px] max-w-full bg-surface border-l border-border shadow-2xl z-50 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-surface shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={onClose}
            className="text-text-muted hover:text-text text-lg leading-none"
          >
            &times;
          </button>
          <button
            onClick={onPrev}
            className="text-text-muted hover:text-text text-[12px] border border-border rounded px-1.5 py-0.5"
          >
            &#9668; Prev
          </button>
          <button
            onClick={onNext}
            className="text-text-muted hover:text-text text-[12px] border border-border rounded px-1.5 py-0.5"
          >
            Next &#9658;
          </button>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[11px] text-text-muted font-mono">{handId}</span>
          <button
            onClick={() => setShowRaw(!showRaw)}
            className={`text-[11px] border rounded px-1.5 py-0.5 transition-colors ${
              showRaw
                ? 'border-primary text-primary bg-primary/10'
                : 'border-border text-text-muted hover:border-text-muted'
            }`}
          >
            Raw
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        {loading ? (
          <p className="text-text-muted text-sm">Loading...</p>
        ) : !hand ? (
          <p className="text-text-muted text-sm">Hand not found.</p>
        ) : showRaw ? (
          <pre className="text-[12px] font-mono text-text whitespace-pre-wrap break-words bg-background rounded p-3 border border-border">
            {hand.raw_text || 'No raw text available.'}
          </pre>
        ) : (
          <>
            {/* Meta */}
            <div className="mb-3">
              <div className="text-[14px] font-semibold text-text">
                {formatStakes(hand.bb_amount)}{' '}
                <span className="text-text-muted font-normal">({hand.stakes})</span>
              </div>
              <div className="text-[12px] text-text-muted">
                {new Date(hand.played_at).toLocaleString()}
                {' \u2022 '}
                {hand.table_size}-max
                {hand.table_name && <> {' \u2022 '} {hand.table_name}</>}
              </div>
            </div>

            {/* Players */}
            <div className="mb-3">
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="border-b border-border text-text-muted">
                    <th className="py-0.5 px-1 text-left font-medium">Seat</th>
                    <th className="py-0.5 px-1 text-left font-medium">Pos</th>
                    <th className="py-0.5 px-1 text-left font-medium">Player</th>
                    <th className="py-0.5 px-1 text-right font-medium">Stack</th>
                    <th className="py-0.5 px-1 text-left font-medium">Cards</th>
                  </tr>
                </thead>
                <tbody>
                  {hand.players.map((p) => (
                    <tr
                      key={p.seat}
                      className={`border-b border-border/30 ${p.is_hero ? 'bg-primary/5' : ''}`}
                    >
                      <td className="py-0.5 px-1 font-mono text-text-muted">{p.seat}</td>
                      <td className="py-0.5 px-1 font-mono">{p.position}</td>
                      <td className={`py-0.5 px-1 ${p.is_hero ? 'font-semibold text-primary' : 'text-text'}`}>
                        {p.username}
                      </td>
                      <td className="py-0.5 px-1 text-right font-mono">{p.stack_bb.toFixed(1)}</td>
                      <td className="py-0.5 px-1">
                        <CardPair card1={p.card1} card2={p.card2} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Actions */}
            <HandActionsDisplay actions={hand.actions} board={hand.board} />

            {/* Result */}
            <div className={`my-3 text-[14px] font-bold font-mono ${heroWonBb >= 0 ? 'text-green' : 'text-red'}`}>
              Hero {heroWonBb >= 0 ? 'wins' : 'loses'} {Math.abs(heroWonBb).toFixed(1)} BB
            </div>

            {/* Tags */}
            <div className="mb-3">
              <div className="flex items-center gap-1.5 flex-wrap">
                {hand.tags.map((t) => (
                  <TagPill key={t} tag={t} onRemove={() => handleRemoveTag(t)} />
                ))}
                <TagPicker
                  currentTags={hand.tags}
                  onAdd={handleAddTag}
                  onRemove={handleRemoveTag}
                />
              </div>
            </div>

            {/* Notes */}
            <div>
              <div className="text-[11px] uppercase tracking-wider text-text-muted mb-1">Notes</div>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={3}
                className="w-full bg-background border border-border rounded px-2 py-1.5 text-[12px] text-text placeholder:text-text-muted outline-none focus:border-primary resize-y"
                placeholder="Add notes about this hand..."
              />
              <div className="flex justify-end mt-1">
                <button
                  onClick={handleNoteSave}
                  disabled={noteSaving || note === (hand.note || '')}
                  className="text-[11px] px-2 py-0.5 rounded bg-primary text-white hover:bg-primary-hover disabled:opacity-30 disabled:cursor-default"
                >
                  {noteSaving ? 'Saving...' : 'Save'}
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
