import { useState, type ReactNode } from 'react';
import { StatValue } from '@/components/ui/stat-value';
import { Chip, chipToneClasses, type ChipTone } from '@/components/ui/chip';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Link } from 'react-router-dom';

/** Every class name is a literal so Tailwind sees it. */
const SURFACES: [string, string][] = [
  ['background', 'bg-background'],
  ['surface-sunken', 'bg-surface-sunken'],
  ['card', 'bg-card'],
  ['surface-raised', 'bg-surface-raised'],
  ['muted', 'bg-muted'],
  ['primary', 'bg-primary'],
  ['selection', 'bg-selection'],
  ['overlay-hover', 'bg-overlay-hover'],
  ['overlay-selected', 'bg-overlay-selected'],
  ['overlay-focus', 'bg-overlay-focus'],
];

const TEXT_LEVELS: [string, string][] = [
  ['foreground', 'text-foreground'],
  ['muted-foreground', 'text-muted-foreground'],
  ['subtle-foreground', 'text-subtle-foreground'],
  ['sample', 'text-sample'],
  ['primary', 'text-primary'],
  ['money-pos', 'text-money-pos'],
  ['money-neg', 'text-money-neg'],
  ['money-zero', 'text-money-zero'],
];

const GROUPS: { title: string; items: [string, string][] }[] = [
  {
    title: 'Positions',
    items: [
      ['pos-ep', 'bg-pos-ep'], ['pos-mp', 'bg-pos-mp'], ['pos-co', 'bg-pos-co'],
      ['pos-btn', 'bg-pos-btn'], ['pos-sb', 'bg-pos-sb'], ['pos-bb', 'bg-pos-bb'],
    ],
  },
  {
    title: 'Streets',
    items: [['street-flop', 'bg-street-flop'], ['street-turn', 'bg-street-turn'], ['street-river', 'bg-street-river']],
  },
  {
    title: 'Actions',
    items: [
      ['act-fold', 'bg-act-fold'], ['act-check', 'bg-act-check'], ['act-call', 'bg-act-call'],
      ['act-bet', 'bg-act-bet'], ['act-raise', 'bg-act-raise'], ['act-allin', 'bg-act-allin'],
    ],
  },
  {
    title: 'Suits',
    items: [['suit-s', 'bg-suit-s'], ['suit-h', 'bg-suit-h'], ['suit-d', 'bg-suit-d'], ['suit-c', 'bg-suit-c']],
  },
  {
    title: 'Chart series',
    items: [
      ['chart-main', 'bg-chart-main'], ['chart-ev', 'bg-chart-ev'], ['chart-sd', 'bg-chart-sd'],
      ['chart-nsd', 'bg-chart-nsd'], ['chart-rake', 'bg-chart-rake'], ['chart-axis', 'bg-chart-axis'],
      ['chart-grid', 'bg-chart-grid'],
    ],
  },
  {
    title: 'Tags',
    items: [
      ['tag-1', 'bg-tag-1'], ['tag-2', 'bg-tag-2'], ['tag-3', 'bg-tag-3'], ['tag-4', 'bg-tag-4'], ['tag-5', 'bg-tag-5'],
      ['tag-6', 'bg-tag-6'], ['tag-7', 'bg-tag-7'], ['tag-8', 'bg-tag-8'], ['tag-9', 'bg-tag-9'],
    ],
  },
];

const TYPE_SCALE: [string, string][] = [
  ['text-2xs (10/14)', 'text-2xs'],
  ['text-label (11/16)', 'text-label'],
  ['text-xs', 'text-xs'],
  ['text-cell (13/18)', 'text-cell'],
  ['text-sm', 'text-sm'],
  ['text-lg', 'text-lg'],
  ['text-xl', 'text-xl'],
];

const RADII: [string, string][] = [
  ['rounded-cell 2px', 'rounded-cell'],
  ['rounded-control 4px', 'rounded-control'],
  ['rounded-card 8px', 'rounded-card'],
  ['rounded-pill', 'rounded-pill'],
];

const HEIGHTS: [string, string][] = [
  ['h-row-dense 26', 'h-row-dense'],
  ['h-row 30', 'h-row'],
  ['h-row-tree 32', 'h-row-tree'],
  ['h-row-header 28', 'h-row-header'],
  ['h-control 28', 'h-control'],
  ['h-button 30', 'h-button'],
];

const TONES: ChipTone[] = Object.keys(chipToneClasses) as ChipTone[];

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="border-b border-border-subtle pb-1 text-sm font-medium">{title}</h2>
      {children}
    </section>
  );
}

function Swatch({ name, cls }: { name: string; cls: string }) {
  return (
    <div className="flex w-32 flex-col gap-1">
      <div className={`h-10 rounded-control border border-border ${cls}`} />
      <div className="text-2xs text-muted-foreground">{name}</div>
    </div>
  );
}

const TAB_NAMES = [
  'Overview', 'Preflop', 'Flop', 'Turn', 'River', 'Showdown',
  'Positions', 'Sessions', 'Players', 'Tags', 'Notes', 'Settings',
];

export default function DesignPage() {
  const [tab, setTab] = useState('Overview');
  const [chips, setChips] = useState(['Btn vs BB', '3-bet pots', 'Last 30 days']);

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-8 pb-16">
      <h1 className="text-xl">Design tokens and primitives</h1>

      <Section title="Colour roles">
        <div className="flex flex-wrap gap-3">
          {SURFACES.map(([n, c]) => <Swatch key={n} name={n} cls={c} />)}
        </div>
        {GROUPS.map((g) => (
          <div key={g.title} className="flex flex-col gap-1">
            <div className="text-label text-muted-foreground">{g.title}</div>
            <div className="flex flex-wrap gap-3">
              {g.items.map(([n, c]) => <Swatch key={n} name={n} cls={c} />)}
            </div>
          </div>
        ))}
      </Section>

      <Section title="Text levels">
        <div className="flex flex-col gap-1 rounded-card bg-card p-3">
          {TEXT_LEVELS.map(([n, c]) => (
            <div key={n} className={`text-sm ${c}`}>{n}: The quick brown fox 0123456789</div>
          ))}
        </div>
      </Section>

      <Section title="Type scale">
        <div className="flex flex-col gap-1">
          {TYPE_SCALE.map(([n, c]) => <div key={n} className={c}>{n}: Hand 1234567890</div>)}
          <div className="font-mono text-xs text-muted-foreground">font-mono: Seat 1: Hero ($10 in chips)</div>
        </div>
      </Section>

      <Section title="Radii">
        <div className="flex flex-wrap gap-3">
          {RADII.map(([n, c]) => (
            <div key={n} className="flex flex-col gap-1">
              <div className={`size-14 border border-border bg-surface-raised ${c}`} />
              <div className="text-2xs text-muted-foreground">{n}</div>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Row and control heights">
        <div className="flex flex-col gap-1">
          {HEIGHTS.map(([n, c]) => (
            <div key={n} className="flex items-center gap-3">
              <div className={`w-48 rounded-control bg-surface-raised px-2 text-cell leading-none ${c} flex items-center`}>{n}</div>
            </div>
          ))}
        </div>
      </Section>

      <Section title="StatValue">
        <div className="grid grid-cols-[10rem_1fr] items-center gap-x-4 gap-y-1 text-cell">
          <span className="text-muted-foreground">normal (23.4%, 140)</span>
          <StatValue value={23.4} sample={140} />
          <span className="text-muted-foreground">low sample (40%, 12)</span>
          <StatValue value={40} sample={12} />
          <span className="text-muted-foreground">dimmed (40%, 6)</span>
          <StatValue value={40} sample={6} />
          <span className="text-muted-foreground">forced sample (40%, 300)</span>
          <StatValue value={40} sample={300} showSample />
          <span className="text-muted-foreground">null</span>
          <StatValue value={null} />
          <span className="text-muted-foreground">bb/100 positive</span>
          <StatValue value={12.6} sample={900} format="bb100" tone="pos" />
          <span className="text-muted-foreground">bb/100 negative</span>
          <StatValue value={-5.43} sample={900} format="bb100" tone="neg" />
          <span className="text-muted-foreground">bb/100 zero</span>
          <StatValue value={0} sample={900} format="bb100" tone="zero" />
          <span className="text-muted-foreground">number (hands)</span>
          <StatValue value={12500} format="number" tone="muted" />
        </div>
      </Section>

      <Section title="Chip">
        <div className="flex flex-wrap items-center gap-2">
          {TONES.map((t) => <Chip key={t} tone={t}>{t}</Chip>)}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {TONES.map((t) => <Chip key={t} tone={t} size="sm" dot>{t}</Chip>)}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Chip dot tone="pos">dot</Chip>
          <Chip nonDefault tone="accent">non-default</Chip>
          <Chip tone="neutral" onClick={() => {}}>clickable</Chip>
          {chips.map((c) => (
            <Chip key={c} tone="accent" onClick={() => {}} onRemove={() => setChips((cs) => cs.filter((x) => x !== c))}>
              {c}
            </Chip>
          ))}
          {chips.length === 0 && <span className="text-xs text-subtle-foreground">all removed, reload to reset</span>}
        </div>
      </Section>

      <Section title="Tabs, line variant with overflow (container is 420px wide)">
        <div className="w-[420px] max-w-full">
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList variant="line" overflow>
              {TAB_NAMES.map((n, i) => (
                <TabsTrigger key={n} value={n} marker={i === 2} count={i === 1 ? 24 : undefined}>
                  {n}
                </TabsTrigger>
              ))}
            </TabsList>
            <TabsContent value={tab} className="py-2 text-sm text-muted-foreground">
              Active tab: {tab}
            </TabsContent>
          </Tabs>
        </div>
        <div className="w-full">
          <Tabs defaultValue="a">
            <TabsList variant="line">
              <TabsTrigger value="a">Wide, no overflow</TabsTrigger>
              <TabsTrigger value="b" marker>Marker</TabsTrigger>
              <TabsTrigger value="c" count={3}>Count</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
      </Section>

      <Section title="Full-width demos">
        <p className="text-sm text-muted-foreground">
          <Link className="text-primary underline-offset-4 hover:underline" to="/design/data-grid">Data grid</Link>
          {' · '}
          <Link className="text-primary underline-offset-4 hover:underline" to="/design/page-chain">Page chain</Link>
        </p>
      </Section>
    </div>
  );
}
