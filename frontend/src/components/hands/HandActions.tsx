import type { HandAction, BoardCards } from '@/lib/api';
import { CardBoxRow } from './CardDisplay';

const ACTION_COLORS: Record<string, string> = {
  fold: 'text-text-muted',
  check: 'text-text',
  call: 'text-green',
  bet: 'text-yellow-400',
  raise: 'text-red',
  post_sb: 'text-text-muted',
  post_bb: 'text-text-muted',
  post_ante: 'text-text-muted',
};

function StreetSection({
  label,
  actions,
  boardCards,
}: {
  label: string;
  actions: HandAction[];
  boardCards: string[];
}) {
  return (
    <div className="mb-3">
      {/* Street header with board cards */}
      <div className="flex items-center gap-3 mb-1.5 pb-1 border-b border-border/30">
        <span className="text-[12px] font-bold uppercase tracking-wider text-text-muted">
          {label}
        </span>
        {boardCards.length > 0 && <CardBoxRow cards={boardCards} />}
      </div>
      {/* Action lines — position badge first, then name, then action */}
      {actions.length > 0 ? (
        <div className="space-y-0.5">
          {actions.map((a, i) => (
            <div key={i} className="text-[13px] font-mono leading-relaxed flex items-center gap-1.5">
              <span className="text-[11px] font-mono font-bold text-text bg-surface-hover rounded px-1.5 py-px shrink-0 min-w-[28px] text-center">
                {a.position}
              </span>
              <span className={`truncate max-w-[100px] ${a.is_hero ? 'text-primary font-semibold' : 'text-text-muted'}`}>
                {a.player}
              </span>
              <span className={ACTION_COLORS[a.action] || 'text-text'}>
                {a.action}
              </span>
              {a.amount_bb !== null && a.amount_bb !== undefined && (
                <span className="text-text">{a.amount_bb.toFixed(1)} BB</span>
              )}
              {a.is_all_in && (
                <span className="text-red text-[10px] font-bold uppercase tracking-wide">
                  all-in
                </span>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="text-[12px] text-text-muted/40 italic">No action</div>
      )}
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
  const streets: { key: string; label: string; cards: string[]; reached: boolean }[] = [
    { key: 'preflop', label: 'Preflop', cards: [], reached: true },
    { key: 'flop', label: 'Flop', cards: board.flop, reached: board.flop.length > 0 || actions.some((a) => a.street === 'flop') },
    { key: 'turn', label: 'Turn', cards: [...board.flop, ...board.turn], reached: board.turn.length > 0 || actions.some((a) => a.street === 'turn') },
    { key: 'river', label: 'River', cards: [...board.flop, ...board.turn, ...board.river], reached: board.river.length > 0 || actions.some((a) => a.street === 'river') },
  ];

  return (
    <div>
      {streets.filter((s) => s.reached).map((s) => (
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
