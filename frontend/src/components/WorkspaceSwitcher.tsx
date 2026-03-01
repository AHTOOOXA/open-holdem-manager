import { ChevronsUpDown, Plus, Settings2 } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { useWorkspace } from '@/contexts/WorkspaceContext';
import { useSidebar } from '@/components/ui/sidebar';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from '@/components/ui/tooltip';

function ColorDot({ color, size = 'sm' }: { color: string | null; size?: 'sm' | 'md' }) {
  return (
    <span
      className={`inline-block shrink-0 rounded-full ${size === 'md' ? 'size-2.5' : 'size-2'}`}
      style={{ backgroundColor: color ?? '#6b7280' }}
    />
  );
}

function formatCount(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k`;
  return String(n);
}

export default function WorkspaceSwitcher() {
  const { workspaces, activeWorkspaceId, activeWorkspace, setActiveWorkspaceId } = useWorkspace();
  const { state, isMobile } = useSidebar();

  const isCollapsed = state === 'collapsed' && !isMobile;

  const dropdownContent = (
    <DropdownMenuContent side="right" align="start" className="w-52">
      {workspaces.map((ws) => {
        const isActive = ws.id === activeWorkspaceId;
        return (
          <DropdownMenuItem
            key={ws.id}
            onClick={() => setActiveWorkspaceId(ws.id)}
            className={`flex items-center gap-2 ${isActive ? 'bg-sidebar-accent' : ''}`}
          >
            <ColorDot color={ws.color} size="md" />
            <span className="flex-1 truncate">{ws.name}</span>
            {ws.hand_count > 0 && (
              <span className="text-[11px] text-muted-foreground tabular-nums">
                {formatCount(ws.hand_count)}
              </span>
            )}
          </DropdownMenuItem>
        );
      })}
      <DropdownMenuSeparator />
      <DropdownMenuItem asChild>
        <NavLink to="/settings/workspaces" className="flex items-center gap-2">
          <Plus className="size-3.5" />
          <span>New Workspace</span>
        </NavLink>
      </DropdownMenuItem>
      <DropdownMenuItem asChild>
        <NavLink to="/settings/workspaces" className="flex items-center gap-2">
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
