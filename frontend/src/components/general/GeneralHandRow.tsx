import type { CSSProperties, ReactNode } from 'react';
import { cn, formatStakes } from '@/lib/utils';
import { usd } from '@/lib/format';
import TagChip from '@/components/marked/TagChip';
import { ContextMenu, ContextMenuContent, ContextMenuTrigger } from '@/components/ui/context-menu';
import type { ActionToken, HandRow, StreetCell } from '@/lib/api-general';
import {
  cardParts,
  formatBbAmount,
  formatHandDate,
  formatSignedBb,
  HAND_STREETS,
  positionClass,
  splitTokens,
  suitClass,
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

/** A card as a small tile filled with its suit token (four-colour deck), rank in white. */
export function CardTile({ card }: { card: string }) {
  const p = cardParts(card);
  if (!p) return null;
  const name = cardName(card);
  return (
    <span
      role="img"
      aria-label={name}
      className={cn(
        'inline-flex h-[22px] w-4 shrink-0 items-center justify-center rounded-cell text-sm leading-none text-white',
        suitClass(p.suit),
      )}
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

/** Dashed 2px underline in the token's own colour (currentColor), drawn as a background so the dash pattern is fixed. */
const HERO_UNDERLINE: CSSProperties = {
  backgroundImage: 'repeating-linear-gradient(to right, currentColor 0 4px, transparent 4px 6px)',
  backgroundSize: '100% 2px',
  backgroundPosition: '0 100%',
  backgroundRepeat: 'no-repeat',
  paddingBottom: 3,
};

function Token({ a }: { a: ActionToken }) {
  const text = tokenText(a);
  return (
    <span
      className={cn('whitespace-nowrap', positionClass(a.pos))}
      style={a.hero ? HERO_UNDERLINE : undefined}
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
          className="cursor-pointer rounded-cell text-muted-foreground underline decoration-dotted underline-offset-4 outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-primary"
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

/** Won column: green for a win, red for a loss, neutral for exactly zero. */
function wonClass(won: number): string {
  return won > 0 ? 'text-money-pos' : won < 0 ? 'text-money-neg' : 'text-money-zero';
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
  /** Single mouse click: select the row only (a drawer opened by the first click of a double click is closed by the second). */
  onSelect: (handId: string) => void;
  /** Double click or keyboard activation of the hole-cards button: open the replayer. */
  onOpen: (handId: string) => void;
  /** Right-click menu items (ContextMenuItem children). */
  menu?: ReactNode;
  onMenuCloseAutoFocus?: (event: Event) => void;
}

/**
 * One hand in H2N's list notation (H2N-COMPATIBLE-STATS.md 6.7): hand value,
 * hole cards, preflop actions, then per street the new board cards, the pot at the start
 * of the street (bb) and the actions. Tokens are coloured by the actor's
 * position; the stat owner's are underlined with a dashed line. Streets after
 * the player folded stay blank.
 */
export default function GeneralHandRow({ row, expandedStreets, onExpandStreet, selected, onSelect, onOpen, menu, onMenuCloseAutoFocus }: GeneralHandRowProps) {
  const won = row.won_bb;
  const ev = row.ev_diff_bb;
  const tr = (
    // Plain table row: the whole row is a mouse target for convenience, while
    // keyboard and screen-reader users get one real button (the hole cards).
    // The +N buttons sit in other cells, so no control is nested in another.
    <tr
      data-hand-id={row.hand_id}
      aria-current={selected ? 'true' : undefined}
      onClick={() => onSelect(row.hand_id)}
      onDoubleClick={() => onOpen(row.hand_id)}
      className={cn(
        'cursor-pointer border-b border-border',
        selected ? 'bg-selection' : 'hover:bg-overlay-hover focus-within:bg-overlay-hover',
      )}
      style={{ height: 38.67 }}
    >
      <Td className="pl-4 text-muted-foreground">
        <Stacked>
          {row.hand_value.map((v, i) => (
            <span key={i}>{v.label}</span>
          ))}
        </Stacked>
      </Td>
      <Td>
        <button
          type="button"
          className="inline-flex cursor-pointer rounded-control align-middle outline-none focus-visible:ring-2 focus-visible:ring-primary"
          aria-label={`Open hand${row.hole_cards.length ? ` ${row.hole_cards.map(cardName).join(', ')}` : ''}${row.played_at ? `, ${formatHandDate(row.played_at)}` : ''}`}
          onClick={(e) => {
            e.stopPropagation();
            // detail 0 = Enter / Space; a mouse click only selects (double click opens)
            if (e.detail === 0) onOpen(row.hand_id);
            else onSelect(row.hand_id);
          }}
        >
          {row.hole_cards.length ? <CardGroup cards={row.hole_cards} /> : <span className="text-subtle-foreground">??</span>}
        </button>
        {row.tags && row.tags.length > 0 && (
          <span className="ml-2 inline-flex items-center gap-1 align-middle">
            {row.tags.slice(0, 2).map((t) => (
              <TagChip key={t.id} tag={t} />
            ))}
            {row.tags.length > 2 && <span className="text-2xs text-muted-foreground">+{row.tags.length - 2}</span>}
          </span>
        )}
      </Td>
      {row.error ? (
        // Spans exactly the street cells: preflop actions + (cards, pot, actions) x 3 streets.
        <td colSpan={1 + 3 * (HAND_STREETS.length - 1)} className="px-[5px] text-sm text-subtle-foreground">
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
              <Td key={`${name}-p`} className="text-foreground">
                <span title={st.pot != null ? usd(st.pot) : undefined}>
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
      <Td className="pl-3 text-muted-foreground">{row.stakes ? formatStakes(row.stakes) : ''}</Td>
      <Td className={cn('text-right tabular-nums', won != null && wonClass(won))}>
        <span title={row.won != null ? usd(row.won) : undefined}>{formatSignedBb(won)}</span>
      </Td>
      <Td className="text-right text-muted-foreground tabular-nums">
        {ev != null && Math.abs(ev) > 1e-9 ? formatSignedBb(ev) : ''}
      </Td>
      <Td className="pr-4 text-muted-foreground">{formatHandDate(row.played_at)}</Td>
    </tr>
  );
  if (!menu) return tr;
  return (
    <ContextMenu>
      <ContextMenuTrigger asChild>{tr}</ContextMenuTrigger>
      <ContextMenuContent onCloseAutoFocus={onMenuCloseAutoFocus}>{menu}</ContextMenuContent>
    </ContextMenu>
  );
}
