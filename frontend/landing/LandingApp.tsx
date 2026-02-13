import { QueryClientProvider, QueryClient } from '@tanstack/react-query';
import { ImportProvider } from '@/contexts/ImportContext';
import HeroSection from './components/HeroSection';
import ShowcaseGraph from './components/ShowcaseGraph';
import ShowcaseStats from './components/ShowcaseStats';
import ShowcaseHands from './components/ShowcaseHands';
import FeatureGrid from './components/FeatureGrid';
import Footer from './components/Footer';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: Infinity,
      gcTime: Infinity,
      refetchOnWindowFocus: false,
      retry: false,
    },
  },
});

export default function LandingApp() {
  return (
    <QueryClientProvider client={queryClient}>
      <ImportProvider>
        <div className="min-h-screen bg-background text-text">
          <HeroSection />

          <section className="max-w-7xl mx-auto px-4 sm:px-6 py-16 space-y-20">
            {/* Graph showcase */}
            <div className="space-y-4">
              <div className="text-center">
                <h2 className="text-2xl font-bold text-text">Track Your Results</h2>
                <p className="text-text-muted mt-1">Interactive graph with EV lines, session markers, and breakdowns by stakes, position, and month.</p>
              </div>
              <ShowcaseGraph />
            </div>

            {/* Stats showcase */}
            <div className="space-y-4">
              <div className="text-center">
                <h2 className="text-2xl font-bold text-text">Analyze Your Stats</h2>
                <p className="text-text-muted mt-1">70+ poker stats with positional breakdowns, benchmark coloring, and drift detection.</p>
              </div>
              <ShowcaseStats />
            </div>

            {/* Hands showcase */}
            <div className="space-y-4">
              <div className="text-center">
                <h2 className="text-2xl font-bold text-text">Browse Every Hand</h2>
                <p className="text-text-muted mt-1">Filter by position, stakes, result, tags. See actions inline with card displays.</p>
              </div>
              <ShowcaseHands />
            </div>
          </section>

          <FeatureGrid />

          {/* Download CTA */}
          <section className="py-16 text-center">
            <h2 className="text-2xl font-bold text-text mb-2">Ready to track your game?</h2>
            <p className="text-text-muted mb-6">Free, open-source, no account required.</p>
            <div className="flex items-center justify-center gap-3">
              <a
                href="https://github.com/AHTOOOXA/open-holdem-manager/releases/latest"
                className="inline-flex items-center gap-2 px-6 py-3 bg-primary text-white rounded-lg font-semibold hover:bg-primary/90 transition-colors"
              >
                Download
              </a>
              <a
                href="https://github.com/AHTOOOXA/open-holdem-manager"
                className="inline-flex items-center gap-2 px-6 py-3 bg-surface border border-border text-text rounded-lg font-semibold hover:bg-surface-hover transition-colors"
              >
                View on GitHub
              </a>
            </div>
          </section>

          <Footer />
        </div>
      </ImportProvider>
    </QueryClientProvider>
  );
}
