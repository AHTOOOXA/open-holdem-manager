import { useState, useEffect, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { HandDetail } from '@/lib/api';
import { updateNote } from '@/lib/api';
import { handDetailQuery } from '@/components/hands/handDetailQuery';
import { queryKeys } from '@/lib/query-keys';
import { HandPlayersTable, HandResultLine } from './HandTextParts';
import HandActionsDisplay from './HandActions';
import HandReplayer from './replayer/HandReplayer';
import TagChip from '@/components/marked/TagChip';
import TagPickerPopover from '@/components/marked/TagPickerPopover';
import { useMarkHand, useTagDefs } from '@/components/marked/useMarkHand';
import { formatStakes } from '@/lib/utils';
import { plotPlayers, rowPlayer } from '@/lib/hands/hand-plot';
import { getShareUrl, anonymizeHand } from '@/lib/hand-codec';
import { RitBadge, CashoutBadge } from '@/components/hands/HandTypeBadge';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { Share2, Check, EyeOff, Eye } from 'lucide-react';
export type HandViewMode = 'visual' | 'text' | 'raw';
type ViewMode = HandViewMode;

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
      {hand.rit_boards > 1 && <RitBadge boards={hand.rit_boards} />}
      {hand.is_cashout && <CashoutBadge />}
    </div>
  );
}

export default function HandDrawer({
  handId,
  playerId,
  onClose,
  onPrev,
  onNext,
  onTagsChanged,
  onCloseAutoFocus,
  initialMode = 'visual',
  evBb,
}: {
  handId: string;
  /** The row's player (hand lists that mix players). */
  playerId?: number;
  onClose: () => void;
  onPrev: () => void;
  onNext: () => void;
  /** After a mark / tag change in the drawer (the hand lists and the detail are refreshed already). */
  onTagsChanged?: () => void;
  /** Radix focus-restore hook: preventDefault() it to place focus yourself. */
  onCloseAutoFocus?: (event: Event) => void;
  /** View the drawer opens in (the replayer by default). */
  initialMode?: HandViewMode;
  /** The row's all-in EV (bb), shown on the result line when it differs from the result. */
  evBb?: number | null;
}) {
  // The shared detail cache (panel, quick replay, history dialog): j/k onto a hand seen there is instant.
  // Mark / tag changes patch and refresh that entry (useMarkHand); a saved note is written into it.
  const qc = useQueryClient();
  const { data, isPending: loading } = useQuery(handDetailQuery(handId, playerId));
  const hand = useMemo<HandDetail | null>(() => (data ? { ...data, tags: data.tags ?? [] } : null), [data]);
  const [viewMode, setViewMode] = useState<ViewMode>(initialMode);
  // The note being edited, per hand: until edited it shows the stored note.
  const noteKey = `${handId}:${playerId ?? ''}`;
  const [draft, setDraft] = useState<{ key: string; text: string } | null>(null);
  const note = draft?.key === noteKey ? draft.text : (hand?.note || '');
  const setNote = (text: string) => setDraft({ key: noteKey, text });
  const [noteSaving, setNoteSaving] = useState(false);
  const [copied, setCopied] = useState(false);
  const [anonymized, setAnonymized] = useState(false);

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

  const { mark, unmark } = useMarkHand();
  const tagDefCount = useTagDefs().length;
  const [pickerOpen, setPickerOpen] = useState(false);

  const handleMark = async () => {
    if (!hand) return;
    if (await mark(hand.id, undefined, playerId)) onTagsChanged?.();
  };
  const handleUnmark = async () => {
    if (!hand) return;
    if (await unmark(hand.id, playerId)) onTagsChanged?.();
  };
  const handlePickerClose = () => {
    // the picker saves as it goes (each save patches and refreshes the cached detail)
    setPickerOpen(false);
    onTagsChanged?.();
  };

  const handleNoteSave = async () => {
    if (!hand) return;
    const id = hand.id;
    const text = note;
    setNoteSaving(true);
    try {
      await updateNote(id, text);
      // A note belongs to the hand: every cached view of it (any row player)
      qc.setQueriesData<HandDetail>({ queryKey: queryKeys.hands.detail(id) }, (old) => (old ? { ...old, note: text } : old));
    } finally {
      setNoteSaving(false);
    }
  };

  const handleShare = async () => {
    if (!hand) return;
    const url = getShareUrl(anonymized ? anonymizeHand(hand) : hand);
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const displayHand = hand && anonymized ? anonymizeHand(hand) : hand;
  const owner = displayHand ? rowPlayer(displayHand.players, playerId) : undefined;
  const heroWonBb = owner?.won_bb ?? 0;

  return (
    <Sheet open={true} onOpenChange={(open) => { if (!open) onClose(); }}>
      <SheetContent side="right" showCloseButton={false} onCloseAutoFocus={onCloseAutoFocus} className="w-full !max-w-none p-0 flex flex-col sm:w-[880px]">
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
                className={`h-8 w-8 p-0 ${anonymized ? 'text-primary' : ''}`}
                onClick={() => setAnonymized((v) => !v)}
                title={anonymized ? 'Show real names' : 'Anonymize names'}
              >
                {anonymized ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </Button>
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
                  <HandReplayer hand={displayHand!} />
                  <div className="mt-4" />
                </>

              /* ── Text view ─────────────────────────────────────── */
              ) : (
                <>
                  <MetaHeader hand={hand} />

                  {/* Players — position-first */}
                  <div className="mb-4">
                    <HandPlayersTable players={plotPlayers(displayHand!, playerId)} />
                  </div>

                  {/* Actions */}
                  <HandActionsDisplay actions={displayHand!.actions} board={displayHand!.board} extraBoards={displayHand!.extra_boards} />

                  {/* Result */}
                  <div className="mt-1 mb-4">
                    <HandResultLine wonBb={heroWonBb} evBb={evBb} isCashout={hand.is_cashout} />
                  </div>
                </>
              )}

              {/* ── Marked state + tags (all views) ──────────────── */}
              <div className="mb-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs text-muted-foreground">{hand.marked ? 'Marked' : 'Not marked'}</span>
                  {(hand.tags ?? []).map((t) => (
                    <TagChip key={t.id} tag={t} size="md" />
                  ))}
                  {!hand.marked && (
                    <Button variant="outline" size="sm" className="h-6 px-2 text-xs" onClick={handleMark}>
                      Mark
                    </Button>
                  )}
                  {tagDefCount > 0 && (
                    <span className="relative inline-flex">
                      <Button variant="outline" size="sm" className="h-6 px-2 text-xs" onClick={() => setPickerOpen(true)}>
                        Tags…
                      </Button>
                      {pickerOpen && (
                        <TagPickerPopover handId={hand.id} playerId={playerId} initialTags={hand.tags ?? []} onClose={handlePickerClose}>
                          <span aria-hidden className="absolute inset-0" />
                        </TagPickerPopover>
                      )}
                    </span>
                  )}
                  {hand.marked && (
                    <Button variant="outline" size="sm" className="h-6 px-2 text-xs" onClick={handleUnmark}>
                      Unmark
                    </Button>
                  )}
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
