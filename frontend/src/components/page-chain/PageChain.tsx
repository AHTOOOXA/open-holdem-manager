/**
 * PageChain: Hand2Note-style row of pages, each opened by a click on the one to its left.
 *
 * <PageChain
 *   pages={chain.pages}                       // Page<I,S>[] from lib/page-chain
 *   renderPage={(page, i, level) => node}     // body of page i; level = { upper, lower } classNames
 *   renderHeader0={() => node}                // page 0's header (dashboard header); pages 1+ get title chip + close X
 *   onClose={i => ...}                        // close page i and everything right of it
 *   onSelectionCleared={k => ...}             // called with i-1 on close, to clear the left page's highlighted row
 *   onResize={(i, px) => ...}                 // stored on release (and on keyboard steps)
 *   trailing={node} onCloseTrailing={...}     // optional pseudo-page at the far right (e.g. a 500px hand panel)
 *   trailingTitle="Hand" trailingWidth={500}
 * />
 *
 * Levels: three alternating surfaces, card -> surface-raised -> surface-sunken. Page i's upper area
 * uses level i%3, its lower block (usePageLevel().lower) uses (i+1)%3, so a lower block always
 * differs from its own page and matches the next page's upper area.
 *
 * Focus: a newly opened (or reused) page 1+ moves focus to its header; page 0 and
 * Escape are left alone (Hand2Note has no Escape-to-close).
 */
import {
  createContext, useCallback, useContext, useEffect, useRef, useState,
  type KeyboardEvent, type PointerEvent, type ReactNode,
} from 'react';
import { X } from 'lucide-react';
import { Chip } from '@/components/ui/chip';
import { cn } from '@/lib/utils';
import {
  KEY_STEP, KEY_STEP_LARGE, LAST_PAGE_BASE_WIDTH, MIN_PAGE_WIDTH,
  leftNeighbourId, levelOf, type Page,
} from '@/lib/page-chain';

export const LEVEL_CLASSES = ['bg-card', 'bg-surface-raised', 'bg-surface-sunken'] as const;

export interface PageLevel {
  upper: string;
  lower: string;
}

const PageLevelContext = createContext<PageLevel>({ upper: LEVEL_CLASSES[0], lower: LEVEL_CLASSES[1] });

/** Background classes for the current page's upper area and lower block. */
export function usePageLevel(): PageLevel {
  return useContext(PageLevelContext);
}

export function levelClasses(index: number): PageLevel {
  const l = levelOf(index);
  return { upper: LEVEL_CLASSES[l.upper], lower: LEVEL_CLASSES[l.lower] };
}

function ResizeHandle({ label, width, onLive, onCommit }: {
  label: string;
  width: number;
  onLive: (px: number | null) => void;
  onCommit: (px: number) => void;
}) {
  const drag = useRef<{ startX: number; startW: number; w: number } | null>(null);

  const onPointerDown = (e: PointerEvent<HTMLDivElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = { startX: e.clientX, startW: width, w: width };
  };
  const onPointerMove = (e: PointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    if (!d) return;
    d.w = Math.max(MIN_PAGE_WIDTH, d.startW + e.clientX - d.startX);
    onLive(d.w);
  };
  const end = () => {
    const d = drag.current;
    drag.current = null;
    if (!d) return;
    onLive(null);
    onCommit(d.w);
  };
  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const step = e.shiftKey ? KEY_STEP_LARGE : KEY_STEP;
    if (e.key === 'ArrowRight') { e.preventDefault(); onCommit(width + step); }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); onCommit(width - step); }
  };

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      aria-valuenow={Math.round(width)}
      aria-valuemin={MIN_PAGE_WIDTH}
      tabIndex={0}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={end}
      onPointerCancel={end}
      onKeyDown={onKeyDown}
      className="absolute inset-y-0 right-0 z-10 w-1.5 cursor-ew-resize touch-none bg-transparent outline-none transition-colors hover:bg-primary/40 focus-visible:bg-primary/60"
    />
  );
}

function PageHeader({ title, onClose, headerRef }: {
  title: string;
  onClose: () => void;
  headerRef: (el: HTMLDivElement | null) => void;
}) {
  return (
    <div ref={headerRef} tabIndex={-1} className="mx-6 mt-4 flex items-center justify-between outline-none">
      <Chip tone="neutral">{title}</Chip>
      <button
        type="button"
        aria-label="Close page"
        onClick={onClose}
        className="inline-flex size-6 items-center justify-center rounded-control text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
      >
        <X className="size-4" aria-hidden />
      </button>
    </div>
  );
}

const boxClass = 'relative flex min-w-[20px] flex-col overflow-x-hidden rounded-card shadow-lg';

export interface PageChainProps<I, S> {
  pages: Page<I, S>[];
  renderPage: (page: Page<I, S>, index: number, level: PageLevel) => ReactNode;
  renderHeader0?: () => ReactNode;
  onClose: (index: number) => void;
  onSelectionCleared?: (index: number) => void;
  onResize: (index: number, px: number) => void;
  trailing?: ReactNode;
  trailingTitle?: string;
  trailingWidth?: number;
  onCloseTrailing?: () => void;
  className?: string;
}

export function PageChain<I, S>({
  pages, renderPage, renderHeader0, onClose, onSelectionCleared, onResize,
  trailing, trailingTitle = 'Details', trailingWidth = 500, onCloseTrailing, className,
}: PageChainProps<I, S>) {
  const [live, setLive] = useState<{ id: number; px: number } | null>(null);
  const headers = useRef(new Map<number, HTMLDivElement>());
  const sections = useRef(new Map<number, HTMLElement>());
  const seen = useRef<Map<number, number> | null>(null);

  // Focus the header of a page the first time it is opened or each time it is reused.
  useEffect(() => {
    const prev = seen.current;
    const next = new Map(pages.map((p) => [p.id, p.rev]));
    seen.current = next;
    if (!prev) return;
    for (let i = pages.length - 1; i >= 1; i--) {
      const p = pages[i];
      if (prev.get(p.id) !== p.rev) { headers.current.get(p.id)?.focus(); break; }
    }
  }, [pages]);

  // Focus a page by id: its header (pages 1+) or else its section
  const focusPage = useCallback((id: number | null) => {
    if (id === null) return;
    (headers.current.get(id) ?? sections.current.get(id))?.focus();
  }, []);

  const close = useCallback((i: number) => {
    // The X is about to unmount: hand focus to the page on the left first
    focusPage(leftNeighbourId(pages, i));
    onClose(i);
    onSelectionCleared?.(i - 1);
  }, [pages, focusPage, onClose, onSelectionCleared]);

  const last = pages.length - 1;
  return (
    <div className={cn('flex items-stretch gap-4 overflow-x-auto', className)}>
      {pages.map((page, i) => {
        const level = levelClasses(i);
        const isLast = i === last;
        const w = live && live.id === page.id ? live.px : page.width;
        return (
          <section
            key={page.id}
            aria-label={page.title}
            ref={(el) => { if (el) sections.current.set(page.id, el); else sections.current.delete(page.id); }}
            tabIndex={-1}
            className={cn(boxClass, 'outline-none', level.upper, isLast ? 'grow' : 'shrink-0')}
            style={{
              zIndex: 100 - i,
              width: isLast ? undefined : w,
              minWidth: isLast ? LAST_PAGE_BASE_WIDTH : undefined,
            }}
          >
            {i === 0 ? renderHeader0?.() : (
              <PageHeader
                title={page.title}
                onClose={() => close(i)}
                headerRef={(el) => { if (el) headers.current.set(page.id, el); else headers.current.delete(page.id); }}
              />
            )}
            <PageLevelContext.Provider value={level}>{renderPage(page, i, level)}</PageLevelContext.Provider>
            {!isLast && (
              <ResizeHandle
                label={`Resize ${page.title}`}
                width={w}
                onLive={(px) => setLive(px === null ? null : { id: page.id, px })}
                onCommit={(px) => onResize(i, px)}
              />
            )}
          </section>
        );
      })}
      {trailing && (
        <section
          aria-label={trailingTitle}
          className={cn(boxClass, 'shrink-0', levelClasses(pages.length).upper)}
          style={{ zIndex: 100 - pages.length, width: trailingWidth }}
        >
          <div className="mx-6 mt-4 flex items-center justify-between">
            <Chip tone="neutral">{trailingTitle}</Chip>
            {onCloseTrailing && (
              <button
                type="button"
                aria-label="Close panel"
                onClick={() => { focusPage(pages[last]?.id ?? null); onCloseTrailing(); }}
                className="inline-flex size-6 items-center justify-center rounded-control text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
              >
                <X className="size-4" aria-hidden />
              </button>
            )}
          </div>
          <PageLevelContext.Provider value={levelClasses(pages.length)}>{trailing}</PageLevelContext.Provider>
        </section>
      )}
    </div>
  );
}
