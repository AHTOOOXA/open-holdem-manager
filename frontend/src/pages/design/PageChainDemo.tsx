import { useState } from 'react';
import { PageChain, usePageLevel } from '@/components/page-chain/PageChain';
import { usePageChain } from '@/lib/page-chain';
import { cn } from '@/lib/utils';

interface Inherited { parent: string }
interface PState { selected: string | null }

const ITEMS = ['Alpha', 'Bravo', 'Charlie', 'Delta', 'Echo'];

function Body({ items, selected, onPick }: {
  items: string[];
  selected: string | null;
  onPick: (item: string) => void;
}) {
  const { lower } = usePageLevel();
  return (
    <div className="flex min-h-64 flex-1 flex-col">
      <ul className="m-6 flex flex-col gap-1">
        {items.map((it) => (
          <li key={it}>
            <button
              type="button"
              aria-pressed={selected === it}
              onClick={() => onPick(it)}
              className={cn(
                'w-full rounded-control px-3 py-1.5 text-left text-sm hover:bg-muted',
                selected === it && 'bg-primary/15 text-primary',
              )}
            >
              {it}
            </button>
          </li>
        ))}
      </ul>
      <div className={cn('mt-auto p-4 text-xs text-muted-foreground', lower)}>Lower block</div>
    </div>
  );
}

export default function PageChainDemo() {
  const c = usePageChain<Inherited, PState>({ title: 'Overview', inherited: { parent: '' }, state: { selected: null } });
  const [showHand, setShowHand] = useState(false);

  return (
    <div className="flex flex-col gap-3 p-4">
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={showHand} onChange={(e) => setShowHand(e.target.checked)} />
        Show trailing panel
      </label>
      <p className="text-xs text-muted-foreground">
        Widths: {c.pages.map((p, i) => `#${i} ${i === c.pages.length - 1 ? 'fill' : `${p.width}px`}`).join(' · ')}
      </p>
      <PageChain
        pages={c.pages}
        renderHeader0={() => <h2 className="mx-6 mt-4 text-sm font-medium">Dashboard header</h2>}
        renderPage={(page, i) => (
          <Body
            items={ITEMS.map((x) => (i === 0 ? x : `${page.inherited.parent}/${x}`))}
            selected={page.state.selected}
            onPick={(item) => {
              c.setState(i, { selected: item });
              c.open(i, { title: item, inherited: { parent: item }, state: { selected: null } });
            }}
          />
        )}
        onClose={c.close}
        onSelectionCleared={(k) => { if (k >= 0) c.setState(k, { selected: null }); }}
        onResize={c.resize}
        trailing={showHand ? <p className="m-6 text-sm">Hand panel (500px)</p> : undefined}
        onCloseTrailing={() => setShowHand(false)}
        trailingTitle="Hand"
      />
    </div>
  );
}
