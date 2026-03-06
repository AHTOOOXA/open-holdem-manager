import { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import type { HandDetail, HandAction, BoardCards } from '@/lib/api';

/**
 * Build per-slot extra board cards from BoardCards, inheriting shared cards from Board 1.
 * Returns an array of 5 cards (or fewer if board is shorter).
 */
function buildFullExtraBoard(board1Cards: string[], extraBoard: BoardCards): string[] {
  const flop = extraBoard.flop.length > 0 ? extraBoard.flop : board1Cards.slice(0, 3);
  const turn = extraBoard.turn.length > 0 ? extraBoard.turn : board1Cards.slice(3, 4);
  const river = extraBoard.river.length > 0 ? extraBoard.river : board1Cards.slice(4, 5);
  return [...flop, ...turn, ...river];
}

// ── Types ────────────────────────────────────────────────────────────

export interface PlayerSnapshot {
  username: string;
  position: string;
  stack: number;       // current stack in BB
  card1: string | null;
  card2: string | null;
  isFolded: boolean;
  isAllIn: boolean;
  lastAction: string | null;   // e.g. "raise 6.0 BB"
  currentBet: number;  // current street bet in BB
  wonBb: number;       // net result in BB
  collectedBb: number; // gross collected in BB (0 during action steps, filled at Result)
  isHero: boolean;
}

export interface Snapshot {
  pot: number;          // total pot in BB
  players: PlayerSnapshot[];
  board: string[];      // revealed community cards (always Board 1)
  board2Cards?: Record<number, string>;  // slot index → Board 2 card for diverging slots (RIT)
  activePlayerIdx: number | null;
  streetLabel: string;  // "Preflop", "Flop", etc.
  actionIdx: number;    // index in the original actions array (-1 for initial/street-transition)
  isStreetTransition: boolean;
}

export interface ReplayerState {
  snapshots: Snapshot[];
  currentStep: number;
  isPlaying: boolean;
  speed: number;        // multiplier: 0.5, 1, 2, 3
  play: () => void;
  pause: () => void;
  togglePlay: () => void;
  stepForward: () => void;
  stepBack: () => void;
  goToStart: () => void;
  goToEnd: () => void;
  goToStep: (step: number) => void;
  setSpeed: (speed: number) => void;
  current: Snapshot;
}

// ── Helpers ──────────────────────────────────────────────────────────

const STREET_ORDER = ['preflop', 'flop', 'turn', 'river'] as const;
const STREET_LABELS: Record<string, string> = {
  preflop: 'Preflop',
  flop: 'Flop',
  turn: 'Turn',
  river: 'River',
};

function buildBoard(board: HandDetail['board'], street: string): string[] {
  const cards: string[] = [];
  if (STREET_ORDER.indexOf(street as typeof STREET_ORDER[number]) >= 1) {
    cards.push(...board.flop);
  }
  if (STREET_ORDER.indexOf(street as typeof STREET_ORDER[number]) >= 2) {
    cards.push(...board.turn);
  }
  if (STREET_ORDER.indexOf(street as typeof STREET_ORDER[number]) >= 3) {
    cards.push(...board.river);
  }
  return cards;
}

// ── Snapshot Builder ─────────────────────────────────────────────────

function buildSnapshots(hand: HandDetail): Snapshot[] {
  const snapshots: Snapshot[] = [];

  // Order players by seat number, then rotate so hero is at index 0 (bottom center).
  // This preserves correct relative positions around the table.
  const bySeat = [...hand.players].sort((a, b) => a.seat - b.seat);
  const heroIdx = bySeat.findIndex(p => p.is_hero);
  const orderedPlayers = heroIdx >= 0
    ? [...bySeat.slice(heroIdx), ...bySeat.slice(0, heroIdx)]
    : bySeat;

  const initialPlayers: PlayerSnapshot[] = orderedPlayers.map(p => ({
    username: p.username,
    position: p.position,
    stack: p.stack_bb,
    card1: p.is_hero ? p.card1 : null,
    card2: p.is_hero ? p.card2 : null,
    isFolded: false,
    isAllIn: false,
    lastAction: null,
    currentBet: 0,
    wonBb: p.won_bb,
    collectedBb: 0,
    isHero: p.is_hero,
  }));

  // Build a username→index map for quick lookups
  const nameToIdx: Record<string, number> = {};
  orderedPlayers.forEach((p, i) => { nameToIdx[p.username] = i; });

  let pot = 0;
  let players = initialPlayers.map(p => ({ ...p }));

  // Group actions by street
  const actionsByStreet: Record<string, HandAction[]> = {};
  for (const a of hand.actions) {
    if (!actionsByStreet[a.street]) actionsByStreet[a.street] = [];
    actionsByStreet[a.street].push(a);
  }

  // Process blind/ante postings from actions to set up initial state
  const blindTypes = new Set(['post_sb', 'post_bb', 'post_ante']);
  const preflopActions = actionsByStreet['preflop'] || [];
  const blindPostings = preflopActions.filter(a => blindTypes.has(a.action));
  // Remove blind postings from preflop so they aren't processed as regular actions
  actionsByStreet['preflop'] = preflopActions.filter(a => !blindTypes.has(a.action));

  for (const bp of blindPostings) {
    const bpName = bp.is_hero
      ? orderedPlayers.find(p => p.is_hero)?.username
      : bp.player;
    const bpIdx = bpName ? nameToIdx[bpName] : undefined;
    if (bpIdx !== undefined) {
      const amt = bp.amount_bb ?? 0;
      players[bpIdx].stack -= amt;
      players[bpIdx].currentBet += amt;
      pot += amt;
    }
  }

  // Initial snapshot (before any action)
  snapshots.push({
    pot,
    players: players.map(p => ({ ...p })),
    board: [],
    activePlayerIdx: null,
    streetLabel: 'Preflop',
    actionIdx: -1,
    isStreetTransition: false,
  });

  let actionCounter = 0;
  for (const street of STREET_ORDER) {
    const streetActions = actionsByStreet[street] || [];
    // Skip streets that weren't reached: no actions AND no new cards dealt for this street
    const streetHasCards = street === 'flop' ? hand.board.flop.length > 0
      : street === 'turn' ? hand.board.turn.length > 0
      : street === 'river' ? hand.board.river.length > 0
      : false;
    if (street !== 'preflop' && streetActions.length === 0 && !streetHasCards) {
      continue;
    }

    // Street transition snapshot (new board cards revealed)
    if (street !== 'preflop') {
      // Reset current bets for new street
      players = players.map(p => ({ ...p, currentBet: 0, lastAction: null }));
      const board = buildBoard(hand.board, street);
      snapshots.push({
        pot,
        players: players.map(p => ({ ...p })),
        board,
        activePlayerIdx: null,
        streetLabel: STREET_LABELS[street] || street,
        actionIdx: -1,
        isStreetTransition: true,
      });
    }

    // Process each action
    for (const action of streetActions) {
      // Find the player who acted
      // Actions have player="Hero" for hero and the actual username for villains
      const playerName = action.is_hero
        ? orderedPlayers.find(p => p.is_hero)?.username
        : action.player;
      const pIdx = playerName ? nameToIdx[playerName] : undefined;

      if (pIdx !== undefined) {
        const p = players[pIdx];
        const prevBet = p.currentBet;

        switch (action.action) {
          case 'fold':
            p.isFolded = true;
            p.lastAction = 'Fold';
            break;
          case 'check':
            p.lastAction = 'Check';
            break;
          case 'call': {
            const callAmt = (action.amount_bb ?? 0);
            p.stack -= callAmt;
            p.currentBet = prevBet + callAmt;
            pot += callAmt;
            p.lastAction = `Call ${callAmt.toFixed(1)}`;
            break;
          }
          case 'bet': {
            const betAmt = (action.amount_bb ?? 0);
            p.stack -= betAmt;
            p.currentBet = betAmt;
            pot += betAmt;
            p.lastAction = `Bet ${betAmt.toFixed(1)}`;
            break;
          }
          case 'raise': {
            // amount_bb is the "to" amount for the raise
            const raiseToAmt = (action.amount_bb ?? 0);
            const increment = raiseToAmt - prevBet;
            p.stack -= increment;
            p.currentBet = raiseToAmt;
            pot += increment;
            p.lastAction = `Raise ${raiseToAmt.toFixed(1)}`;
            break;
          }
        }

        if (action.is_all_in) {
          p.isAllIn = true;
          p.lastAction = (p.lastAction || '') + ' all-in';
        }
      }

      snapshots.push({
        pot,
        players: players.map(p => ({ ...p })),
        board: buildBoard(hand.board, street),
        activePlayerIdx: pIdx ?? null,
        streetLabel: STREET_LABELS[street] || street,
        actionIdx: actionCounter,
        isStreetTransition: false,
      });

      actionCounter++;
    }
  }

  // RIT transition players — reveal cards, clear action/bet state
  const ritPlayers = players.map((p, i) => {
    const orig = orderedPlayers[i];
    return {
      ...p,
      card1: orig.card1,
      card2: orig.card2,
      lastAction: null,
      currentBet: 0,
    };
  });

  // Result players — reveal cards + show gross collected for all collectors
  const showdownPlayers = players.map((p, i) => {
    const orig = orderedPlayers[i];
    const investedBb = orig.stack_bb - p.stack;
    const collectedBb = Math.max(0, p.wonBb + investedBb);
    return {
      ...p,
      card1: orig.card1,
      card2: orig.card2,
      collectedBb,
      currentBet: 0,
      lastAction: collectedBb > 0 ? `Won ${collectedBb.toFixed(1)}` : p.isFolded ? 'Fold' : null,
    };
  });

  const finalBoard = buildBoard(hand.board, 'river');
  const resultBoard = finalBoard.length > 0 ? finalBoard : buildBoard(hand.board, 'flop');

  // RIT transition snapshots — animate each extra board street-by-street
  // board always stays as Board 1; board2Cards accumulates Board 2 diverging slots
  let ritBoard2Cards: Record<number, string> | undefined;

  if (hand.extra_boards && hand.extra_boards.length > 0) {
    for (let ebIdx = 0; ebIdx < hand.extra_boards.length; ebIdx++) {
      const extraBoard = hand.extra_boards[ebIdx];
      const fullExtra = buildFullExtraBoard(resultBoard, extraBoard);
      const boardLabel = hand.extra_boards.length > 1 ? ` (${ebIdx + 2})` : ' (2)';

      // Find diverging slots grouped by street
      const diverging: { slotIdx: number; board2Card: string; street: string }[] = [];
      for (let s = 0; s < Math.min(resultBoard.length, fullExtra.length); s++) {
        if (fullExtra[s] !== resultBoard[s]) {
          const street = s < 3 ? 'Flop' : s === 3 ? 'Turn' : 'River';
          diverging.push({ slotIdx: s, board2Card: fullExtra[s], street });
        }
      }

      if (diverging.length === 0) continue;

      // Group by street, preserving order
      const streetGroups: { street: string; slots: { slotIdx: number; board2Card: string }[] }[] = [];
      for (const d of diverging) {
        const last = streetGroups[streetGroups.length - 1];
        if (last && last.street === d.street) {
          last.slots.push(d);
        } else {
          streetGroups.push({ street: d.street, slots: [d] });
        }
      }

      // Accumulate board2Cards progressively across streets
      const acc: Record<number, string> = ritBoard2Cards ? { ...ritBoard2Cards } : {};

      for (const group of streetGroups) {
        for (const slot of group.slots) {
          acc[slot.slotIdx] = slot.board2Card;
        }

        snapshots.push({
          pot,
          players: ritPlayers.map(p => ({ ...p })),
          board: resultBoard,
          board2Cards: { ...acc },
          activePlayerIdx: null,
          streetLabel: `${group.street}${boardLabel}`,
          actionIdx: -1,
          isStreetTransition: true,
        });
      }

      ritBoard2Cards = { ...acc };
    }
  }

  snapshots.push({
    pot,
    players: showdownPlayers.map(p => ({ ...p })),
    board: resultBoard,
    board2Cards: ritBoard2Cards,
    activePlayerIdx: null,
    streetLabel: 'Result',
    actionIdx: -1,
    isStreetTransition: false,
  });

  return snapshots;
}

// ── Hook ─────────────────────────────────────────────────────────────

export function useReplayerState(hand: HandDetail): ReplayerState {
  const snapshots = useMemo(() => buildSnapshots(hand), [hand]);
  const [currentStep, setCurrentStep] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const maxStep = snapshots.length - 1;

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const stepForward = useCallback(() => {
    setCurrentStep(s => Math.min(s + 1, maxStep));
  }, [maxStep]);

  const stepBack = useCallback(() => {
    setCurrentStep(s => Math.max(s - 1, 0));
  }, []);

  const goToStart = useCallback(() => {
    setCurrentStep(0);
    setIsPlaying(false);
    clearTimer();
  }, [clearTimer]);

  const goToEnd = useCallback(() => {
    setCurrentStep(maxStep);
    setIsPlaying(false);
    clearTimer();
  }, [maxStep, clearTimer]);

  const goToStep = useCallback((step: number) => {
    setCurrentStep(Math.max(0, Math.min(step, maxStep)));
  }, [maxStep]);

  const pause = useCallback(() => {
    setIsPlaying(false);
    clearTimer();
  }, [clearTimer]);

  const play = useCallback(() => {
    setIsPlaying(true);
  }, []);

  const togglePlay = useCallback(() => {
    setIsPlaying(p => !p);
  }, []);

  // Auto-advance when playing — uses timeout callback (not direct setState in effect body)
  useEffect(() => {
    if (!isPlaying || currentStep >= maxStep) {
      return;
    }

    const nextSnapshot = snapshots[currentStep + 1];
    const baseDelay = 800 / speed;
    const delay = nextSnapshot?.isStreetTransition ? baseDelay * 1.5 : baseDelay;

    timerRef.current = setTimeout(() => {
      setCurrentStep(s => {
        const next = s + 1;
        if (next >= maxStep) {
          setIsPlaying(false);
        }
        return Math.min(next, maxStep);
      });
    }, delay);

    return () => clearTimer();
  }, [isPlaying, currentStep, maxStep, speed, snapshots, clearTimer]);

  // Reset when hand changes
  const handId = hand.id;
  useEffect(() => {
    setCurrentStep(0); // eslint-disable-line react-hooks/set-state-in-effect -- legitimate reset on prop change
    setIsPlaying(false);
    clearTimer();
  }, [handId, clearTimer]);

  return {
    snapshots,
    currentStep,
    isPlaying,
    speed,
    play,
    pause,
    togglePlay,
    stepForward,
    stepBack,
    goToStart,
    goToEnd,
    goToStep,
    setSpeed,
    current: snapshots[currentStep] || snapshots[0],
  };
}
