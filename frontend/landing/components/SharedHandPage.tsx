import { useSearchParams } from 'react-router-dom';
import { decodeHand } from '@/lib/hand-codec';
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
    <div className="h-screen bg-background text-text flex flex-col">
      {/* Header */}
      <header className="border-b border-border bg-surface shrink-0">
        <div className="max-w-7xl mx-auto px-4 py-2.5 flex items-center justify-between">
          <a href="/#/" className="text-sm font-bold text-primary hover:underline">
            Open Holdem Manager
          </a>
          <a
            href="https://github.com/AHTOOOXA/open-holdem-manager/releases/latest"
            className="px-3 py-1.5 bg-primary text-white rounded-md text-xs font-semibold hover:bg-primary/90 transition-colors"
          >
            Download
          </a>
        </div>
      </header>

      {/* Two-column layout */}
      <main className="flex-1 min-h-0 max-w-7xl w-full mx-auto flex gap-4 px-4 py-3">
        {/* Left: Replayer */}
        <div className="flex-1 min-w-0 flex flex-col">
          <HandReplayer hand={hand} />
        </div>

        {/* Right: Action log */}
        <div className="w-[340px] shrink-0 overflow-y-auto border-l border-border pl-4">
          <HandActionsDisplay actions={hand.actions} board={hand.board} />
          {hero && (
            <div className={`mt-2 text-[14px] font-bold font-mono ${heroWonBb >= 0 ? 'text-green' : 'text-red'}`}>
              Hero {heroWonBb >= 0 ? 'wins' : 'loses'} {Math.abs(heroWonBb).toFixed(1)} BB
            </div>
          )}
        </div>
      </main>

      {/* Footer CTA */}
      <footer className="border-t border-border bg-surface shrink-0">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <p className="text-text-muted text-sm">
            Free, open-source poker tracker — no account, no cloud.
          </p>
          <a
            href="https://github.com/AHTOOOXA/open-holdem-manager/releases/latest"
            className="px-4 py-1.5 bg-primary text-white rounded-md text-sm font-semibold hover:bg-primary/90 transition-colors shrink-0"
          >
            Download Open Holdem Manager
          </a>
        </div>
      </footer>
    </div>
  );
}
