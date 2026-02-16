import { inflateRawSync } from 'node:zlib';

// Mirrors the CompactHand format from src/lib/hand-codec.ts
// Player: [seat, positionIndex, username, stack_bb, card1, card2, won_bb, isHero]
// CompactHand.b: [flop[], turn[], river[]]

const POSITIONS = ['EP', 'MP', 'CO', 'BTN', 'SB', 'BB'] as const;

export interface OgHandData {
  stakes: string;
  bbAmount: number;
  tableSize: number;
  heroName: string;
  heroPosition: string;
  heroCards: [string | null, string | null];
  heroWonBb: number;
  board: string[];
  opponents: { name: string; position: string; cards: [string | null, string | null]; wonBb: number }[];
}

function fromBase64url(str: string): Buffer {
  const padded = str.replace(/-/g, '+').replace(/_/g, '/');
  return Buffer.from(padded, 'base64');
}

export function decodeHandData(encoded: string): OgHandData | null {
  try {
    const compressed = fromBase64url(encoded);
    const json = inflateRawSync(compressed).toString('utf-8');
    const c = JSON.parse(json);
    if (c.v !== 1) return null;

    const heroIdx = c.p.findIndex((p: number[]) => p[7] === 1);
    if (heroIdx === -1) return null;
    const hero = c.p[heroIdx];

    const opponents = c.p
      .filter((_: unknown, i: number) => i !== heroIdx)
      .map((p: (string | number | null)[]) => ({
        name: p[2] as string,
        position: POSITIONS[p[1] as number] ?? 'EP',
        cards: [p[4], p[5]] as [string | null, string | null],
        wonBb: p[6] as number,
      }));

    const board = [...(c.b[0] ?? []), ...(c.b[1] ?? []), ...(c.b[2] ?? [])];

    return {
      stakes: c.s,
      bbAmount: c.bb,
      tableSize: c.ts,
      heroName: hero[2],
      heroPosition: POSITIONS[hero[1]] ?? 'EP',
      heroCards: [hero[4], hero[5]],
      heroWonBb: hero[6],
      board,
      opponents,
    };
  } catch {
    return null;
  }
}
