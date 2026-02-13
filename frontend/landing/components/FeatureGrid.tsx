import { HardDrive, Lock, GitBranch, Zap, BarChart3, CreditCard } from 'lucide-react';

const features = [
  {
    icon: HardDrive,
    title: 'Fully Local',
    description: 'All data stored on your machine. No cloud, no servers, no subscriptions.',
  },
  {
    icon: Lock,
    title: 'Private',
    description: 'Your hand histories never leave your computer. No account required.',
  },
  {
    icon: GitBranch,
    title: 'Open Source',
    description: 'MIT licensed. Fork it, modify it, contribute to it.',
  },
  {
    icon: Zap,
    title: 'Fast Import',
    description: 'Parse thousands of hands in seconds with streaming progress.',
  },
  {
    icon: BarChart3,
    title: '70+ Stats',
    description: 'Pre-flop, post-flop, steal, showdown stats with positional breakdowns.',
  },
  {
    icon: CreditCard,
    title: 'Free Forever',
    description: 'No trial, no premium tier, no ads. Just a free poker tool.',
  },
];

export default function FeatureGrid() {
  return (
    <section className="py-16 bg-surface/30">
      <div className="max-w-5xl mx-auto px-4 sm:px-6">
        <h2 className="text-2xl font-bold text-text text-center mb-10">Why Open Holdem Manager?</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((f) => (
            <div
              key={f.title}
              className="rounded-lg border border-border bg-background p-5 space-y-2"
            >
              <f.icon className="text-primary" size={24} strokeWidth={1.5} />
              <h3 className="text-sm font-semibold text-text">{f.title}</h3>
              <p className="text-sm text-text-muted">{f.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
