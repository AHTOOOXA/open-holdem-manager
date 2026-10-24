import { Link, useParams } from 'react-router-dom';
import { CONFIG_SECTIONS } from '@/components/configuration/sections';
import { findSection, groupSections } from '@/components/configuration/section-registry';
import { cn } from '@/lib/utils';

export default function ConfigurationPage() {
  const { section } = useParams<{ section?: string }>();
  const current = findSection(CONFIG_SECTIONS, section);

  return (
    <div className="flex min-h-0 flex-1 gap-0 overflow-hidden rounded-card border border-border bg-card">
      <nav aria-label="Configuration sections" className="w-52 min-w-[200px] shrink-0 overflow-y-auto border-r border-border py-2">
        {groupSections(CONFIG_SECTIONS).map((g) => (
          <div key={g.group} className="mb-2">
            <div className="px-4 pb-1 pt-2 text-2xs font-medium uppercase tracking-wide text-subtle-foreground">{g.group}</div>
            {g.sections.map((s) => {
              const selected = s.id === current.id;
              return (
                <Link
                  key={s.id}
                  to={`/configuration/${s.id}`}
                  aria-current={selected ? 'page' : undefined}
                  className={cn(
                    'relative flex h-row items-center px-4 text-sm outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-inset',
                    selected ? 'bg-overlay-selected text-foreground' : 'text-muted-foreground hover:bg-overlay-hover hover:text-foreground',
                  )}
                >
                  {selected && <span aria-hidden className="absolute inset-y-0 left-0 w-0.5 bg-primary" />}
                  {s.title}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>
      <div className="flex min-w-0 flex-1 flex-col overflow-y-auto">
        <div className="max-w-3xl p-6" key={current.id}>{current.render()}</div>
      </div>
    </div>
  );
}
