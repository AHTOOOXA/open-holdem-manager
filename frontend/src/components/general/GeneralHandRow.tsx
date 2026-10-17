import type { CSSProperties, ReactNode } from 'react';
import { cn, formatStakes } from '@/lib/utils';
import type { ActionToken, HandRow, StreetCell } from '@/lib/api-general';
import {
  POPUP_THEME,
  SUIT_COLORS,
  cardParts,
  formatBbAmount,
  formatHandDate,
  formatSignedBb,
  HAND_STREETS,
  positionColor,
  splitTokens,
  tokenText,
} from '@/lib/general-notation';
import type { HandStreet } from '@/lib/general-notation';

const RANK_NAMES: Record<string, string> = {
  A: 'Ace',
  K: 'King',
  Q: 'Queen',
  J: 'Jack',
  T: 'Ten',
  '9': 'Nine',
  '8': 'Eight',
  '7': 'Seven',
  '6': 'Six',
  '5': 'Five',
  '4': 'Four',
  '3': 'Three',
  '2': 'Two',
};

const SUIT_NAMES: Record<string, string> = { h: 'hearts', d: 'diamonds', c: 'clubs', s: 'spades' };

/** "Ah" → "Ace of hearts". Falls back to the raw text for anything unexpected. */
export function cardName(card: string): string {
  const p = cardParts(card);
  if (!p) return card;
  const rank = RANK_NAMES[p.rank];
  const suit = SUIT_NAMES[p.suit];
  return rank && suit ? `${rank} of ${suit}` : card;
}

/** A card as a small tile filled with its suit colour (four-colour deck). */
export function CardTile({ card }: { card: string }) {
  const p = cardParts(card);
  if (!p) return null;
  const name = cardName(card);
  return (
    <span
      role="img"
      aria-label={name}
      className="inline-flex h-[22px] w-4 shrink-0 items-center justify-center rounded-[3px] text-[14px] leading-none text-white"
      style={{ background: SUIT_COLORS[p.suit] ?? SUIT_COLORS.s }}
      title={name}
    >
      <span aria-hidden="true">{p.rank}</span>
    </span>
  );
}

function CardGroup({ cards }: { cards: string[] }) {
  return (
    <span className="inline-flex gap-[2px]">
      {cards.map((c, i) => (
        <CardTile key={`${c}-${i}`} card={c} />
      ))}
    </span>
  );
}

/** Dashed 2px underline in the token's colour, drawn as a background so the dash pattern is fixed. */
function heroUnderline(color: string): CSSProperties {
  return {
    backgroundImage: `repeating-linear-gradient(to right, ${color} 0 4px, transparent 4px 6px)`,
    backgroundSize: '100% 2px',
    backgroundPosition: '0 100%',
    backgroundRepeat: 'no-repeat',
    paddingBottom: 3,
  };
}

function Token({ a }: { a: ActionToken }) {
  const color = positionColor(a.pos);
  const text = tokenText(a);
  return (
    <span
      className="whitespace-nowrap"
      style={{ color, ...(a.hero ? heroUnderline(color) : null) }}
      title={`${a.player || a.pos}${a.pos ? ` (${a.pos})` : ''}${a.hero ? ' · hero' : ''}`}
    >
      {text}
    </span>
  );
}

function Actions({
  street,
  expanded,
  onExpand,
}: {
  street: StreetCell;
  expanded: boolean;
  onExpand: () => void;
}) {
  const { shown, hidden } = splitTokens(street.actions, expanded);
  return (
    <span className="inline-flex items-center gap-[6px]">
      {shown.map((a, i) => (
        <Token key={i} a={a} />
      ))}
      {hidden > 0 && (
        <button
          type="button"
          className="cursor-pointer underline decoration-dotted underline-offset-4"
          style={{ color: POPUP_THEME.plusN }}
          title={`Show ${hidden} more action${hidden > 1 ? 's' : ''} on the ${street.street} for every hand`}
          onClick={(e) => {
            e.stopPropagation();
            onExpand();
          }}
        >
          +{hidden}
        </button>
      )}
    </span>
  );
}

function Td({ children, className, style }: { children?: ReactNode; className?: string; style?: CSSProperties }) {
  return (
    <td className={cn('px-[5px] py-0 align-middle whitespace-nowrap', className)} style={style}>
      {children}
    </td>
  );
}

function Stacked({ children }: { children: ReactNode }) {
  return <span className="flex flex-col gap-[2px]">{children}</span>;
}

interface GeneralHandRowProps {
  row: HandRow;
  expandedStreets: ReadonlySet<HandStreet>;
  onExpandStreet: (street: HandStreet) => void;
  selected: boolean;
  onOpen: (handId: string) => void;
}

/**
 * One hand in H2N's list notation (H2N-COMPATIBLE-STATS.md 6.7): hand value,
 * hole cards, preflop actions, then per street the new board cards, the pot at the start
 * of the street (bb) and the actions. Tokens are coloured by the actor's
 * position; the stat owner's are underlined with a dashed line. Streets after
 * the player folded stay blank.
 */
export default function GeneralHandRow({ row, expandedStreets, onExpandStreet, selected, onOpen }: GeneralHandRowProps) {
  const won = row.won_bb;
  const ev = row.ev_diff_bb;
  return (
    // Plain table row: the whole row is a mouse target for convenience, while
    // keyboard and screen-reader users get one real button (the hole cards).
    // The +N buttons sit in other cells, so no control is nested in another.
    <tr
      data-hand-id={row.hand_id}
      aria-current={selected ? 'true' : undefined}
      onClick={() => onOpen(row.hand_id)}
      className={cn('cursor-pointer focus-within:bg-white/5', !selected && 'hover:bg-white/[0.04]')}
      style={{
        height: 38.67,
        borderBottom: `1px solid ${POPUP_THEME.divider}`,
        background: selected ? POPUP_THEME.rowSelected : undefined,
      }}
    >
      <Td className="pl-4" style={{ color: POPUP_THEME.handValue }}>
        <Stacked>
          {row.hand_value.map((v, i) => (
            <span key={i}>{v.label}</span>
          ))}
        </Stacked>
      </Td>
      <Td>
        <button
          type="button"
          className="flex cursor-pointer rounded-[3px] outline-none focus-visible:ring-2 focus-visible:ring-white/60"
          aria-label={`Open hand${row.hole_cards.length ? ` ${row.hole_cards.map(cardName).join(', ')}` : ''}${row.played_at ? `, ${formatHandDate(row.played_at)}` : ''}`}
          onClick={(e) => {
            e.stopPropagation();
            onOpen(row.hand_id);
          }}
        >
          {row.hole_cards.length ? <CardGroup cards={row.hole_cards} /> : <span className="text-white/40">??</span>}
        </button>
      </Td>
      {row.error ? (
        // Spans exactly the street cells: preflop actions + (cards, pot, actions) x 3 streets.
        <td colSpan={1 + 3 * (HAND_STREETS.length - 1)} className="px-[5px] text-sm text-white/40">
          {row.error}
        </td>
      ) : (
        <>
          <Td className="pr-3">
            {row.streets[0] && (
              <Actions
                street={row.streets[0]}
                expanded={expandedStreets.has('preflop')}
                onExpand={() => onExpandStreet('preflop')}
              />
            )}
          </Td>
          {HAND_STREETS.slice(1).map((name, i) => {
            const st = row.streets[i + 1];
            if (!st) {
              return [<Td key={`${name}-c`} className="pl-3" />, <Td key={`${name}-p`} />, <Td key={`${name}-a`} />];
            }
            return [
              <Td key={`${name}-c`} className="pl-3">
                <Stacked>
                  {st.cards.map((g, k) => (
                    <CardGroup key={k} cards={g} />
                  ))}
                </Stacked>
              </Td>,
              <Td key={`${name}-p`} className="text-white">
                <span title={st.pot != null ? `$${st.pot.toFixed(2)}` : undefined}>
                  {st.pot_bb != null ? formatBbAmount(st.pot_bb) : ''}
                </span>
              </Td>,
              <Td key={`${name}-a`} className="pr-3">
                <Actions
                  street={st}
                  expanded={expandedStreets.has(name)}
                  onExpand={() => onExpandStreet(name)}
                />
              </Td>,
            ];
          })}
        </>
      )}
      <Td className="pl-3 text-white/60">{row.stakes ? formatStakes(row.stakes) : ''}</Td>
      <Td
        className="text-right tabular-nums"
        style={{ color: won == null ? undefined : won > 0 ? '#5CC45C' : won < 0 ? '#F57373' : '#D3D3D3' }}
      >
        <span title={row.won != null ? `$${row.won.toFixed(2)}` : undefined}>{formatSignedBb(won)}</span>
      </Td>
      <Td className="text-right text-white/60 tabular-nums">
        {ev != null && Math.abs(ev) > 1e-9 ? formatSignedBb(ev) : ''}
      </Td>
      <Td className="pr-4 text-white/50">{formatHandDate(row.played_at)}</Td>
    </tr>
  );
}
