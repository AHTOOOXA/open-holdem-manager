import type { HandAction, BoardCards } from '@/lib/api';
import { BoardDisplay } from './CardDisplay';

function formatAction(a: HandAction): string {
  let text = a.action;
  if (a.amount_bb !== null && a.amount_bb !== undefined) {
    text += ` ${a.amount_bb.toFixed(1)} BB`;
  }
  if (a.is_all_in) text += ' (all-in)';
  return text;
}

function StreetSection({
  label,
  actions,
  boardCards,
}: {
  label: string;
  actions: HandAction[];
  boardCards: string[];
}) {
  if (actions.length === 0) return null;

  return (
    <div className="mb-3">
      <div className="flex items-center gap-2 mb-1 text-[11px] uppercase tracking-wider text-text-muted border-b border-border/40 pb-1">
        <span className="font-bold">{label}</span>
        {boardCards.length > 0 && (
          <span className="text-[13px] normal-case tracking-normal">
            [<BoardDisplay cards={boardCards} />]
          </span>
        )}
      </div>
      <div className="space-y-0.5">
        {actions.map((a, i) => (
          <div
            key={i}
            className={`text-[13px] font-mono leading-snug ${
              a.is_hero ? 'text-primary' : a.action === 'fold' ? 'text-text-muted' : 'text-text'
            }`}
          >
            <span className={a.is_hero ? 'font-semibold' : ''}>
              {a.player}
            </span>
            <span className="text-text-muted"> ({a.position})</span>
            {': '}
            <span className={a.is_all_in ? 'text-red' : ''}>{formatAction(a)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function HandActionsDisplay({
  actions,
  board,
}: {
  actions: HandAction[];
  board: BoardCards;
}) {
  const streets: { key: string; label: string; cards: string[] }[] = [
    { key: 'preflop', label: 'Preflop', cards: [] },
    { key: 'flop', label: 'Flop', cards: board.flop },
    { key: 'turn', label: 'Turn', cards: [...board.flop, ...board.turn] },
    { key: 'river', label: 'River', cards: [...board.flop, ...board.turn, ...board.river] },
  ];

  return (
    <div>
      {streets.map((s) => (
        <StreetSection
          key={s.key}
          label={s.label}
          actions={actions.filter((a) => a.street === s.key)}
          boardCards={s.cards}
        />
      ))}
    </div>
  );
}
