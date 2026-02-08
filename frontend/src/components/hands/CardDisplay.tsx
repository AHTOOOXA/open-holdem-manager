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
    <span className="font-mono">
      {rank}
      <span className={s.color}>{s.symbol}</span>
    </span>
  );
}

export function CardPair({ card1, card2 }: { card1: string | null; card2: string | null }) {
  if (!card1 || !card2) return <span className="text-text-muted font-mono">--</span>;
  return (
    <span className="font-mono whitespace-nowrap">
      <SingleCard card={card1} />
      {' '}
      <SingleCard card={card2} />
    </span>
  );
}

export function BoardDisplay({ cards }: { cards: string[] }) {
  if (!cards || cards.length === 0) return <span className="text-text-muted font-mono">--</span>;
  return (
    <span className="font-mono whitespace-nowrap">
      {cards.map((c, i) => (
        <span key={i}>
          {i > 0 && ' '}
          <SingleCard card={c} />
        </span>
      ))}
    </span>
  );
}

export default SingleCard;
