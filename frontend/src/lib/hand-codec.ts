import { deflateSync, inflateSync } from 'fflate';
import type { HandDetail, HandPlayerDetail, HandAction, BoardCards } from '@/lib/api';

// ── Lookup tables ────────────────────────────────────────────────────

const POSITIONS = ['EP', 'MP', 'CO', 'BTN', 'SB', 'BB'] as const;
const STREETS = ['preflop', 'flop', 'turn', 'river'] as const;
const ACTIONS = ['fold', 'check', 'call', 'bet', 'raise', 'post_sb', 'post_bb', 'post_ante'] as const;

const posIdx = Object.fromEntries(POSITIONS.map((p, i) => [p, i]));
const streetIdx = Object.fromEntries(STREETS.map((s, i) => [s, i]));
const actionIdx = Object.fromEntries(ACTIONS.map((a, i) => [a, i]));

// ── Compact format types ─────────────────────────────────────────────

// Player: [seat, positionIndex, username, stack_bb, card1, card2, won_bb, isHero]
type CompactPlayer = [number, number, string, number, string | null, string | null, number, number];

// Action: [streetIndex, playerIndex, actionIndex, amount_bb, isAllIn]
type CompactAction = [number, number, number, number | null, number];

interface CompactHand {
  v: 1;
  s: string;       // stakes
  bb: number;       // bb_amount
  ts: number;       // table_size
  p: CompactPlayer[];
  b: [string[], string[], string[]]; // [flop, turn, river]
  a: CompactAction[];
}

// ── Encode ───────────────────────────────────────────────────────────

function toCompact(hand: HandDetail): CompactHand {
  const playerIndex = new Map<string, number>();
  const players: CompactPlayer[] = hand.players.map((p, i) => {
    playerIndex.set(p.username, i);
    return [
      p.seat,
      posIdx[p.position] ?? 0,
      p.username,
      round2(p.stack_bb),
      p.card1,
      p.card2,
      round2(p.won_bb),
      p.is_hero ? 1 : 0,
    ];
  });

  const actions: CompactAction[] = hand.actions.map((a) => [
    streetIdx[a.street] ?? 0,
    playerIndex.get(a.player) ?? 0,
    actionIdx[a.action] ?? 0,
    a.amount_bb !== null && a.amount_bb !== undefined ? round2(a.amount_bb) : null,
    a.is_all_in ? 1 : 0,
  ]);

  return {
    v: 1,
    s: hand.stakes,
    bb: hand.bb_amount,
    ts: hand.table_size,
    p: players,
    b: [hand.board.flop, hand.board.turn, hand.board.river],
    a: actions,
  };
}

function fromCompact(c: CompactHand): HandDetail {
  const players: HandPlayerDetail[] = c.p.map((p) => ({
    seat: p[0],
    position: POSITIONS[p[1]] ?? 'EP',
    username: p[2],
    stack_bb: p[3],
    card1: p[4],
    card2: p[5],
    won_bb: p[6],
    is_hero: p[7] === 1,
    player_type: 'UNK',
  }));

  const actions: HandAction[] = c.a.map((a) => {
    const player = c.p[a[1]];
    return {
      street: STREETS[a[0]] ?? 'preflop',
      player: player?.[2] ?? '',
      position: POSITIONS[player?.[1] ?? 0] ?? 'EP',
      action: ACTIONS[a[2]] ?? 'fold',
      amount_bb: a[3],
      is_all_in: a[4] === 1,
      is_hero: player?.[7] === 1,
    };
  });

  const board: BoardCards = {
    flop: c.b[0] ?? [],
    turn: c.b[1] ?? [],
    river: c.b[2] ?? [],
  };

  return {
    id: 'shared',
    played_at: '',
    stakes: c.s,
    bb_amount: c.bb,
    table_name: null,
    table_size: c.ts,
    raw_text: null,
    players,
    board,
    actions,
    tags: [],
    note: null,
  };
}

// ── Base64url ────────────────────────────────────────────────────────

function toBase64url(bytes: Uint8Array): string {
  let binary = '';
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function fromBase64url(str: string): Uint8Array {
  const padded = str.replace(/-/g, '+').replace(/_/g, '/');
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

// ── Public API ───────────────────────────────────────────────────────

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

export function encodeHand(hand: HandDetail): string {
  const compact = toCompact(hand);
  const json = JSON.stringify(compact);
  const compressed = deflateSync(new TextEncoder().encode(json));
  return toBase64url(compressed);
}

export function decodeHand(encoded: string): HandDetail | null {
  try {
    const compressed = fromBase64url(encoded);
    const json = new TextDecoder().decode(inflateSync(compressed));
    const compact: CompactHand = JSON.parse(json);
    if (compact.v !== 1) return null;
    return fromCompact(compact);
  } catch {
    return null;
  }
}

// ── Anonymize ─────────────────────────────────────────────────────

export function anonymizeHand(hand: HandDetail): HandDetail {
  // Build stable name mapping ordered by seat number; hero keeps real name
  const nameMap = new Map<string, string>();
  let counter = 1;
  const sorted = [...hand.players].sort((a, b) => a.seat - b.seat);
  for (const p of sorted) {
    if (p.is_hero) {
      nameMap.set(p.username, p.username);
    } else {
      nameMap.set(p.username, `Player ${counter}`);
      counter++;
    }
  }

  const players: HandPlayerDetail[] = hand.players.map((p) => ({
    ...p,
    username: nameMap.get(p.username) ?? p.username,
  }));

  const actions: HandAction[] = hand.actions.map((a) => ({
    ...a,
    player: nameMap.get(a.player) ?? a.player,
  }));

  return { ...hand, players, actions };
}

const LANDING_ORIGIN = 'https://ohm.antonchaynik.ru';

export function getShareUrl(hand: HandDetail): string {
  const encoded = encodeHand(hand);
  return `${LANDING_ORIGIN}/#/hand?d=${encoded}`;
}
