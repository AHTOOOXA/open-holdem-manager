import { Bookmark, Pencil, Trash2 } from 'lucide-react';
import type { Workspace } from '@/contexts/WorkspaceContext';
import { Button } from '@/components/ui/button';
import { count, formatMediumDate } from '@/lib/format';
import { cn } from '@/lib/utils';
import ColorDot from './ColorDot';

interface Props {
  workspaces: Workspace[];
  activeId: number;
  onSelect: (id: number) => void;
  onEdit: (ws: Workspace) => void;
  onCheckpoints: (ws: Workspace) => void;
  onDelete: (ws: Workspace) => void;
}

function dateRange(ws: Workspace): string {
  const { min, max } = ws.date_range;
  return min ? `${formatMediumDate(min)} – ${formatMediumDate(max)}` : 'No hands yet';
}

/** Radio-style list: the selected row is the active workspace. */
export default function WorkspaceList({ workspaces, activeId, onSelect, onEdit, onCheckpoints, onDelete }: Props) {
  return (
    <div role="radiogroup" aria-label="Workspaces" className="overflow-hidden rounded-card border border-border bg-card">
      {workspaces.map((ws) => {
        const active = ws.id === activeId;
        return (
          <div
            key={ws.id}
            className={cn(
              'group relative flex min-h-row-tree items-center gap-2 border-b border-border-subtle pr-2 last:border-b-0',
              active ? 'bg-overlay-selected' : 'hover:bg-overlay-hover',
            )}
          >
            {active && <span aria-hidden className="absolute inset-y-0 left-0 w-0.5 bg-primary" />}
            <button
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => onSelect(ws.id)}
              className="flex min-w-0 flex-1 items-center gap-3 py-2 pl-4 text-left outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              <span
                aria-hidden
                className={cn(
                  'flex size-4 shrink-0 items-center justify-center rounded-pill border',
                  active ? 'border-primary' : 'border-subtle-foreground',
                )}
              >
                {active && <span className="size-2 rounded-pill bg-primary" />}
              </span>
              <ColorDot color={ws.color} />
              <span className="min-w-0 flex-1">
                <span className="flex items-baseline gap-2">
                  <span className="truncate text-sm font-medium">{ws.name}</span>
                  {active && <span className="text-2xs uppercase tracking-wide text-primary">Active</span>}
                </span>
                <span className="block truncate text-xs text-muted-foreground">
                  {ws.hero_username ? `Hero: ${ws.hero_username}` : 'No hero yet'}
                  {ws.description ? ` · ${ws.description}` : ''}
                </span>
              </span>
              <span className="hidden shrink-0 text-right text-xs text-muted-foreground sm:block">
                <span className="block text-foreground">{count(ws.hand_count)} hands</span>
                <span className="block">{dateRange(ws)}</span>
              </span>
            </button>
            <div className="flex shrink-0 items-center gap-1 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100">
              <Button size="sm" variant="ghost" className="h-control px-2 text-xs" onClick={() => onEdit(ws)}>
                <Pencil className="size-3" />
                Edit
              </Button>
              <Button size="sm" variant="ghost" className="h-control px-2 text-xs" onClick={() => onCheckpoints(ws)}>
                <Bookmark className="size-3" />
                Checkpoints
              </Button>
              {!active && (
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-control px-2 text-xs text-destructive hover:text-destructive"
                  onClick={() => onDelete(ws)}
                >
                  <Trash2 className="size-3" />
                  Delete
                </Button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
