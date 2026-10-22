import { SUIT_BG, SUIT_BG_FALLBACK } from '@/lib/suits';

// ── Inline card rendering (for detail drawer) ──────────────────────

const SUIT_MAP: Record<string, { symbol: string; color: string }> = {
  s: { symbol: '\u2660', color: 'text-text' },
  h: { symbol: '\u2665', color: 'text-red' },
  d: { symbol: '\u2666', color: 'text-blue' },
  c: { symbol: '\u2663', color: 'text-green' },
};

function SingleCard({ card }: { card: string }) {
  if (!card || card.length < 2) return <span className="text-text-muted">?</span>;
  const rank = card.slice(0, -1).toUpperCase();
  const suit = card.slice(-1).toLowerCase();
  const s = SUIT_MAP[suit];
  if (!s) return <span className="text-text-muted">{card}</span>;
  return (
    <>
      {rank}
      <span className={s.color}>{s.symbol}</span>
    </>
  );
}

export function CardPair({ card1, card2 }: { card1: string | null; card2: string | null }) {
  if (!card1 || !card2) return <span className="text-text-muted">--</span>;
  return (
    <span className="whitespace-nowrap">
      <SingleCard card={card1} />
      {' '}
      <SingleCard card={card2} />
    </span>
  );
}

export function BoardDisplay({ cards }: { cards: string[] }) {
  if (!cards || cards.length === 0) return <span className="text-text-muted">--</span>;
  return (
    <span className="whitespace-nowrap">
      {cards.map((c, i) => (
        <span key={i}>
          {i > 0 && ' '}
          <SingleCard card={c} />
        </span>
      ))}
    </span>
  );
}

// ── H2N-style card boxes (colored background by suit) ───────────────

export function CardBox({ card }: { card: string }) {
  if (!card || card.length < 2) return null;
  const rank = card.slice(0, -1).toUpperCase();
  const suit = card.slice(-1).toLowerCase();
  const bg = SUIT_BG[suit] ?? SUIT_BG_FALLBACK;
  return (
    <span
      className={`inline-flex items-center justify-center w-[30px] h-[34px] rounded-[3px] text-[17px] font-bold text-white leading-none shrink-0 ${bg}`}
    >
      {rank}
    </span>
  );
}

export function CardBoxPair({ card1, card2 }: { card1: string | null; card2: string | null }) {
  if (!card1 || !card2) return null;
  return (
    <span className="inline-flex gap-[2px]">
      <CardBox card={card1} />
      <CardBox card={card2} />
    </span>
  );
}

export function CardBoxRow({ cards }: { cards: string[] }) {
  if (!cards || cards.length === 0) return null;
  return (
    <span className="inline-flex gap-[2px]">
      {cards.map((c, i) => (
        <CardBox key={i} card={c} />
      ))}
    </span>
  );
}

export function CardBack() {
  return (
    <span
      className="inline-flex items-center justify-center w-[30px] h-[34px] rounded-[3px] shrink-0 border border-border/60"
      style={{ backgroundColor: 'oklch(0.22 0.005 260)' }}
    >
      <span className="text-[10px] text-text-muted/40 font-bold select-none">?</span>
    </span>
  );
}

export { SingleCard };
export default SingleCard;
