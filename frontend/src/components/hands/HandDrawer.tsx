import { useState, useEffect, useCallback } from 'react';
import type { HandDetail } from '@/lib/api';
import { getHandDetail, addTag, removeTag, updateNote } from '@/lib/api';
import { CardPair } from './CardDisplay';
import HandActionsDisplay from './HandActions';
import HandReplayer from './replayer/HandReplayer';
import TagPill from './TagPill';
import TagPicker from './TagPicker';
import { formatStakes } from '@/lib/utils';
import { getShareUrl } from '@/lib/hand-codec';
import PlayerTypeBadge from '@/components/PlayerTypeBadge';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { Share2, Check } from 'lucide-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

type ViewMode = 'visual' | 'text' | 'raw';

/* Shared meta header used in visual + text views */
function MetaHeader({ hand }: { hand: HandDetail }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <span className="text-[15px] font-bold text-text">
        {formatStakes(hand.stakes)}
      </span>
      <span className="text-[13px] text-text-muted">
        {new Date(hand.played_at).toLocaleString()}
        {' \u2022 '}
        {hand.table_size}-max
        {hand.table_name && <>{' \u2022 '}{hand.table_name}</>}
      </span>
    </div>
  );
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
  const [viewMode, setViewMode] = useState<ViewMode>('visual');
  const [note, setNote] = useState('');
  const [noteSaving, setNoteSaving] = useState(false);
  const [copied, setCopied] = useState(false);

  const loadHand = useCallback(async () => {
    setLoading(true);
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

  const handleShare = async () => {
    if (!hand) return;
    const url = getShareUrl(hand);
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const hero = hand?.players.find((p) => p.is_hero);
  const heroWonBb = hero?.won_bb ?? 0;

  return (
    <Sheet open={true} onOpenChange={(open) => { if (!open) onClose(); }}>
      <SheetContent side="right" showCloseButton={false} className="w-full !max-w-none p-0 flex flex-col sm:w-[880px]">
        {/* Header */}
        <SheetHeader className="px-4 py-2.5 border-b border-border shrink-0">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="sm" className="h-8 text-sm" onClick={onClose}>
                &times;
              </Button>
              <Button variant="outline" size="sm" className="h-8 text-sm" onClick={onPrev}>
                &#9668; Prev
              </Button>
              <Button variant="outline" size="sm" className="h-8 text-sm" onClick={onNext}>
                Next &#9658;
              </Button>
            </div>
            <div className="flex items-center gap-3">
              <SheetTitle className="text-[12px] text-text-muted font-mono font-normal">{handId}</SheetTitle>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={handleShare}
                title="Copy share link"
              >
                {copied ? <Check className="h-4 w-4 text-green" /> : <Share2 className="h-4 w-4" />}
              </Button>
              <ToggleGroup
                type="single"
                value={viewMode}
                onValueChange={(v) => v && setViewMode(v as ViewMode)}
                className="gap-0"
              >
                <ToggleGroupItem value="visual" className="h-8 px-2.5 text-[12px]">Visual</ToggleGroupItem>
                <ToggleGroupItem value="text" className="h-8 px-2.5 text-[12px]">Text</ToggleGroupItem>
                <ToggleGroupItem value="raw" className="h-8 px-2.5 text-[12px]">Raw</ToggleGroupItem>
              </ToggleGroup>
            </div>
          </div>
        </SheetHeader>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {loading ? (
            <p className="text-text-muted text-sm">Loading...</p>
          ) : !hand ? (
            <p className="text-text-muted text-sm">Hand not found.</p>
          ) : (
            <>
              {/* ── Raw view ─────────────────────────────────────── */}
              {viewMode === 'raw' ? (
                <>
                  <MetaHeader hand={hand} />
                  <pre className="text-[13px] font-mono text-text whitespace-pre-wrap break-words bg-surface rounded-lg p-4 border border-border/40 leading-relaxed">
                    {hand.raw_text || 'No raw text available.'}
                  </pre>
                  <div className="mt-4" />
                </>

              /* ── Visual view ───────────────────────────────────── */
              ) : viewMode === 'visual' ? (
                <>
                  <MetaHeader hand={hand} />
                  <HandReplayer hand={hand} />
                  <div className="mt-4" />
                </>

              /* ── Text view ─────────────────────────────────────── */
              ) : (
                <>
                  <MetaHeader hand={hand} />

                  {/* Players — position-first */}
                  <div className="mb-4">
                    <Table>
                      <TableHeader>
                        <TableRow className="text-[13px]">
                          <TableHead className="py-1.5 px-2 h-auto w-[60px]">Pos</TableHead>
                          <TableHead className="py-1.5 px-2 h-auto">Player</TableHead>
                          <TableHead className="py-1.5 px-2 h-auto text-right">Stack</TableHead>
                          <TableHead className="py-1.5 px-2 h-auto">Cards</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {hand.players.map((p) => (
                          <TableRow
                            key={p.seat}
                            className={`text-[13px] ${p.is_hero ? 'bg-primary/5' : ''}`}
                          >
                            <TableCell className="py-1.5 px-2">
                              <span className="text-[12px] font-mono font-bold text-text bg-surface-hover rounded px-2 py-0.5">
                                {p.position}
                              </span>
                            </TableCell>
                            <TableCell className={`py-1.5 px-2 ${p.is_hero ? 'font-semibold text-primary' : 'text-text-muted'}`}>
                              <span className="flex items-center gap-1.5">
                                {p.username}
                                {!p.is_hero && p.player_type && p.player_type !== 'UNK' && (
                                  <PlayerTypeBadge type={p.player_type} />
                                )}
                              </span>
                            </TableCell>
                            <TableCell className="py-1.5 px-2 text-right font-mono">
                              {p.stack_bb.toFixed(1)}
                            </TableCell>
                            <TableCell className="py-1.5 px-2">
                              <CardPair card1={p.card1} card2={p.card2} />
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>

                  {/* Actions */}
                  <HandActionsDisplay actions={hand.actions} board={hand.board} />

                  {/* Result */}
                  <div className={`mt-1 mb-4 text-[14px] font-bold font-mono ${heroWonBb >= 0 ? 'text-green' : 'text-red'}`}>
                    Hero {heroWonBb >= 0 ? 'wins' : 'loses'} {Math.abs(heroWonBb).toFixed(1)} BB
                  </div>
                </>
              )}

              {/* ── Tags (all views) ─────────────────────────────── */}
              <div className="mb-3">
                <div className="flex items-center gap-2 flex-wrap">
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

              {/* ── Notes (all views) ────────────────────────────── */}
              <div>
                <div className="text-[12px] uppercase tracking-wider text-text-muted mb-1.5">Notes</div>
                <Textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  rows={3}
                  placeholder="Add notes about this hand..."
                  className="text-[13px] resize-y"
                />
                <div className="flex justify-end mt-1.5">
                  <Button
                    size="sm"
                    className="h-7 text-xs"
                    onClick={handleNoteSave}
                    disabled={noteSaving || note === (hand.note || '')}
                  >
                    {noteSaving ? 'Saving...' : 'Save'}
                  </Button>
                </div>
              </div>
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
