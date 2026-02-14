import { useState, useEffect, useCallback } from 'react';
import type { HandDetail } from '@/lib/api';
import { getHandDetail, addTag, removeTag, updateNote } from '@/lib/api';
import { CardPair } from './CardDisplay';
import HandActionsDisplay from './HandActions';
import HandReplayer from './replayer/HandReplayer';
import TagPill from './TagPill';
import TagPicker from './TagPicker';
import { formatStakes } from '@/lib/utils';
import PlayerTypeBadge from '@/components/PlayerTypeBadge';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

type ViewMode = 'visual' | 'text' | 'raw';


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

  const hero = hand?.players.find((p) => p.is_hero);
  const heroWonBb = hero?.won_bb ?? 0;

  return (
    <Sheet open={true} onOpenChange={(open) => { if (!open) onClose(); }}>
      <SheetContent side="right" className={`w-full !max-w-none p-0 flex flex-col [&>button:first-child]:hidden ${viewMode === 'visual' ? 'sm:w-[880px]' : 'sm:w-[640px]'}`}>
        {/* Header */}
        <SheetHeader className="px-4 py-2 border-b border-border shrink-0">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={onClose}>
                &times;
              </Button>
              <Button variant="outline" size="sm" className="h-7 text-xs" onClick={onPrev}>
                &#9668; Prev
              </Button>
              <Button variant="outline" size="sm" className="h-7 text-xs" onClick={onNext}>
                Next &#9658;
              </Button>
            </div>
            <div className="flex items-center gap-3">
              <SheetTitle className="text-[11px] text-text-muted font-mono font-normal">{handId}</SheetTitle>
              <ToggleGroup
                type="single"
                value={viewMode}
                onValueChange={(v) => v && setViewMode(v as ViewMode)}
                className="gap-0"
              >
                <ToggleGroupItem value="visual" className="h-7 px-2 text-[11px]">Visual</ToggleGroupItem>
                <ToggleGroupItem value="text" className="h-7 px-2 text-[11px]">Text</ToggleGroupItem>
                <ToggleGroupItem value="raw" className="h-7 px-2 text-[11px]">Raw</ToggleGroupItem>
              </ToggleGroup>
            </div>
          </div>
        </SheetHeader>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-4 py-3">
          {loading ? (
            <p className="text-text-muted text-sm">Loading...</p>
          ) : !hand ? (
            <p className="text-text-muted text-sm">Hand not found.</p>
          ) : (
            <>
              {/* View mode content */}
              {viewMode === 'raw' ? (
                <pre className="text-[12px] font-mono text-text whitespace-pre-wrap break-words bg-background rounded p-3 border border-border">
                  {hand.raw_text || 'No raw text available.'}
                </pre>
              ) : viewMode === 'visual' ? (
                <>
                  {/* Meta */}
                  <div className="mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-[13px] font-semibold text-text">
                        {formatStakes(hand.stakes)}
                      </span>
                      <span className="text-[11px] text-text-muted">
                        {new Date(hand.played_at).toLocaleString()}
                        {' \u2022 '}
                        {hand.table_size}-max
                      </span>
                    </div>
                  </div>
                  <HandReplayer hand={hand} />
                  {/* Result */}
                  <div className={`my-3 text-[14px] font-bold font-mono ${heroWonBb >= 0 ? 'text-green' : 'text-red'}`}>
                    Hero {heroWonBb >= 0 ? 'wins' : 'loses'} {Math.abs(heroWonBb).toFixed(1)} BB
                  </div>
                </>
              ) : (
                <>
                  {/* Meta */}
                  <div className="mb-3">
                    <div className="text-[14px] font-semibold text-text">
                      {formatStakes(hand.stakes)}
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
                    <Table>
                      <TableHeader>
                        <TableRow className="text-[12px]">
                          <TableHead className="py-0.5 px-1 h-auto">Seat</TableHead>
                          <TableHead className="py-0.5 px-1 h-auto">Pos</TableHead>
                          <TableHead className="py-0.5 px-1 h-auto">Player</TableHead>
                          <TableHead className="py-0.5 px-1 h-auto text-right">Stack</TableHead>
                          <TableHead className="py-0.5 px-1 h-auto">Cards</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {hand.players.map((p) => (
                          <TableRow
                            key={p.seat}
                            className={`text-[12px] ${p.is_hero ? 'bg-primary/5' : ''}`}
                          >
                            <TableCell className="py-0.5 px-1 font-mono text-text-muted">{p.seat}</TableCell>
                            <TableCell className="py-0.5 px-1 font-mono">{p.position}</TableCell>
                            <TableCell className={`py-0.5 px-1 ${p.is_hero ? 'font-semibold text-primary' : 'text-text'}`}>
                              <span className="flex items-center gap-1.5">
                                {p.username}
                                {!p.is_hero && p.player_type && p.player_type !== 'UNK' && (
                                  <PlayerTypeBadge type={p.player_type} />
                                )}
                              </span>
                            </TableCell>
                            <TableCell className="py-0.5 px-1 text-right font-mono">{p.stack_bb.toFixed(1)}</TableCell>
                            <TableCell className="py-0.5 px-1">
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
                  <div className={`my-3 text-[14px] font-bold font-mono ${heroWonBb >= 0 ? 'text-green' : 'text-red'}`}>
                    Hero {heroWonBb >= 0 ? 'wins' : 'loses'} {Math.abs(heroWonBb).toFixed(1)} BB
                  </div>
                </>
              )}

              {/* Tags — visible in all view modes */}
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

              {/* Notes — visible in all view modes */}
              <div>
                <div className="text-[11px] uppercase tracking-wider text-text-muted mb-1">Notes</div>
                <Textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  rows={3}
                  placeholder="Add notes about this hand..."
                  className="text-[12px] resize-y"
                />
                <div className="flex justify-end mt-1">
                  <Button
                    size="sm"
                    className="h-6 text-xs"
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
