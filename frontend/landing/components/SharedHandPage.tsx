import { useSearchParams } from 'react-router-dom';
import { decodeHand } from '@/lib/hand-codec';
import { formatStakes } from '@/lib/utils';
import HandReplayer from '@/components/hands/replayer/HandReplayer';
import HandActionsDisplay from '@/components/hands/HandActions';

export default function SharedHandPage() {
  const [searchParams] = useSearchParams();
  const encoded = searchParams.get('d');

  if (!encoded) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center space-y-3">
          <h1 className="text-xl font-bold text-text">No hand data</h1>
          <p className="text-text-muted text-sm">
            This link is missing the hand data parameter.
          </p>
          <a
            href="/#/"
            className="inline-block text-primary hover:underline text-sm"
          >
            Go to Open Holdem Manager
          </a>
        </div>
      </div>
    );
  }

  const hand = decodeHand(encoded);

  if (!hand) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center space-y-3">
          <h1 className="text-xl font-bold text-text">Invalid hand data</h1>
          <p className="text-text-muted text-sm">
            Could not decode the hand from this URL. The link may be corrupted.
          </p>
          <a
            href="/#/"
            className="inline-block text-primary hover:underline text-sm"
          >
            Go to Open Holdem Manager
          </a>
        </div>
      </div>
    );
  }

  const hero = hand.players.find((p) => p.is_hero);
  const heroWonBb = hero?.won_bb ?? 0;

  return (
    <div className="min-h-screen bg-background text-text">
      {/* Header */}
      <header className="border-b border-border bg-surface">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center justify-between">
          <a href="/#/" className="text-sm font-bold text-primary hover:underline">
            Open Holdem Manager
          </a>
          <div className="flex items-center gap-2 text-sm text-text-muted">
            <span className="font-bold text-text">{formatStakes(hand.stakes)}</span>
            <span>{hand.table_size}-max</span>
          </div>
        </div>
      </header>

      {/* Hand content */}
      <main className="max-w-3xl mx-auto px-4 py-6 space-y-6">
        {/* Replayer */}
        <HandReplayer hand={hand} />

        {/* Actions text view */}
        <HandActionsDisplay actions={hand.actions} board={hand.board} />

        {/* Result */}
        {hero && (
          <div className={`text-[14px] font-bold font-mono ${heroWonBb >= 0 ? 'text-green' : 'text-red'}`}>
            Hero {heroWonBb >= 0 ? 'wins' : 'loses'} {Math.abs(heroWonBb).toFixed(1)} BB
          </div>
        )}
      </main>

      {/* CTA footer */}
      <footer className="border-t border-border mt-12 py-8 text-center">
        <p className="text-text-muted text-sm mb-3">
          Track your own poker hands for free
        </p>
        <a
          href="https://github.com/AHTOOOXA/open-holdem-manager/releases/latest"
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-primary text-white rounded-lg font-semibold text-sm hover:bg-primary/90 transition-colors"
        >
          Download Open Holdem Manager
        </a>
      </footer>
    </div>
  );
}
