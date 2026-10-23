import { ChevronsUpDown, Database, Plus, Settings2 } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { useWorkspace } from '@/contexts/WorkspaceContext';
import { useSidebar } from '@/components/ui/sidebar';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from '@/components/ui/tooltip';
import { count } from '@/lib/format';

const MANAGE_PATH = '/databases';

function ColorDot({ color, size = 'sm' }: { color: string | null; size?: 'sm' | 'md' }) {
  return (
    <span
      className={`inline-block shrink-0 rounded-full ${size === 'md' ? 'size-2.5' : 'size-2'}`}
      style={{ backgroundColor: color ?? '#6b7280' }}
    />
  );
}

/** Workspaces with hand counts; picking one makes it active. */
function WorkspaceItems() {
  const { workspaces, activeWorkspaceId, setActiveWorkspaceId } = useWorkspace();
  return (
    <>
      {workspaces.map((ws) => {
        const isActive = ws.id === activeWorkspaceId;
        return (
          <DropdownMenuItem
            key={ws.id}
            onClick={() => setActiveWorkspaceId(ws.id)}
            className={`flex items-center gap-2 ${isActive ? 'bg-overlay-selected' : ''}`}
            aria-current={isActive ? 'true' : undefined}
          >
            <ColorDot color={ws.color} size="md" />
            <span className="flex-1 truncate">{ws.name}</span>
            <span className="text-xs text-muted-foreground tabular-nums">{count(ws.hand_count)}</span>
          </DropdownMenuItem>
        );
      })}
    </>
  );
}

/** Compact selector for the status bar: database icon, active workspace, chevron. */
function StatusBarWorkspaceSwitcher() {
  const { activeWorkspace } = useWorkspace();
  const name = activeWorkspace?.name ?? 'Select workspace';
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="flex h-6 min-w-0 max-w-56 items-center gap-1.5 rounded-control px-1.5 text-xs text-muted-foreground outline-none hover:bg-overlay-hover hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring data-[state=open]:bg-overlay-selected data-[state=open]:text-foreground"
          aria-label={`Workspace: ${name}`}
        >
          <Database className="size-3.5 shrink-0" />
          <span className="truncate">{name}</span>
          <ChevronsUpDown className="size-3 shrink-0" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent side="top" align="end" className="w-60">
        <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">Workspaces</DropdownMenuLabel>
        <WorkspaceItems />
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <NavLink to={MANAGE_PATH} className="flex items-center gap-2">
            <Settings2 className="size-3.5" />
            <span>Manage workspaces…</span>
          </NavLink>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function SidebarWorkspaceSwitcher() {
  const { activeWorkspace } = useWorkspace();
  const { state, isMobile } = useSidebar();

  const isCollapsed = state === 'collapsed' && !isMobile;

  const dropdownContent = (
    <DropdownMenuContent side="right" align="start" className="w-52">
      <WorkspaceItems />
      <DropdownMenuSeparator />
      <DropdownMenuItem asChild>
        <NavLink to={MANAGE_PATH} className="flex items-center gap-2">
          <Plus className="size-3.5" />
          <span>New Workspace</span>
        </NavLink>
      </DropdownMenuItem>
      <DropdownMenuItem asChild>
        <NavLink to={MANAGE_PATH} className="flex items-center gap-2">
          <Settings2 className="size-3.5" />
          <span>Manage Workspaces</span>
        </NavLink>
      </DropdownMenuItem>
    </DropdownMenuContent>
  );

  if (isCollapsed) {
    return (
      <Tooltip>
        <DropdownMenu>
          <TooltipTrigger asChild>
            <DropdownMenuTrigger asChild>
              <button className="flex size-8 items-center justify-center rounded-md hover:bg-sidebar-accent transition-colors">
                <ColorDot color={activeWorkspace?.color ?? null} size="md" />
              </button>
            </DropdownMenuTrigger>
          </TooltipTrigger>
          <TooltipContent side="right" align="center">
            {activeWorkspace?.name ?? 'Select workspace'}
          </TooltipContent>
          {dropdownContent}
        </DropdownMenu>
      </Tooltip>
    );
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="flex w-full items-center gap-2 rounded-md p-2 h-8 text-sm hover:bg-sidebar-accent transition-colors outline-none">
          <ColorDot color={activeWorkspace?.color ?? null} size="md" />
          <span className="flex-1 truncate text-left font-medium">
            {activeWorkspace?.name ?? 'Select workspace'}
          </span>
          <ChevronsUpDown className="size-3.5 shrink-0 text-muted-foreground" />
        </button>
      </DropdownMenuTrigger>
      {dropdownContent}
    </DropdownMenu>
  );
}

/**
 * Active workspace picker. `variant="statusbar"` is the compact one in the status bar;
 * the default is the old sidebar version (kept for reference, no longer rendered).
 */
export default function WorkspaceSwitcher({ variant = 'sidebar' }: { variant?: 'sidebar' | 'statusbar' }) {
  return variant === 'statusbar' ? <StatusBarWorkspaceSwitcher /> : <SidebarWorkspaceSwitcher />;
}
