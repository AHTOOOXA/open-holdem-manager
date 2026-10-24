import {
  ArrowLeftRight,
  ChartColumn,
  ChartNoAxesCombined,
  Clock,
  Database,
  DollarSign,
  LayoutGrid,
  PanelLeftClose,
  PanelLeftOpen,
  PieChart,
  Settings,
  Star,
  Users,
  type LucideIcon,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { NavLink, useLocation } from 'react-router-dom';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
  useSidebar,
} from '@/components/ui/sidebar';
import { RAIL_LABELS, railPathFor, type RailPath } from '@/lib/routes';
import { useWorkspace } from '@/contexts/WorkspaceContext';
import { useSessionsLive } from '@/hooks/useSessionsLive';

interface RailItem {
  to: RailPath;
  icon: LucideIcon;
}

const mainItems: RailItem[] = [
  { to: '/reports', icon: ChartColumn },
  { to: '/statistics', icon: LayoutGrid },
  { to: '/sessions', icon: Clock },
  { to: '/marked', icon: Star },
];

const extraItems: RailItem[] = [
  { to: '/extras/stats', icon: ChartNoAxesCombined },
  { to: '/extras/compare', icon: ArrowLeftRight },
  { to: '/extras/cash-drop', icon: DollarSign },
  { to: '/extras/population', icon: PieChart },
  { to: '/extras/players', icon: Users },
];

const systemItems: RailItem[] = [
  { to: '/databases', icon: Database },
  { to: '/configuration', icon: Settings },
];

/** Red "LIVE" pill on the Sessions item; a dot on the collapsed rail (only one of the two is rendered by CSS). */
function LiveBadge() {
  return (
    <>
      <Badge
        variant="destructive"
        aria-hidden
        className="ml-auto rounded-cell px-1 py-0 text-2xs font-semibold uppercase group-data-[collapsible=icon]:hidden"
      >
        Live
      </Badge>
      <span className="sr-only">live session</span>
      <span
        aria-hidden
        className="absolute top-1 right-1 hidden size-2 rounded-pill bg-destructive group-data-[collapsible=icon]:block"
      />
    </>
  );
}

function RailLink({ item, active, live }: { item: RailItem; active: boolean; live?: boolean }) {
  const label = RAIL_LABELS[item.to];
  return (
    <SidebarMenuItem>
      {/* Selected marker: 2px accent bar on the rail's left edge (the group pads by 8px) */}
      {active && <span aria-hidden className="absolute inset-y-1 -left-2 w-0.5 rounded-r-cell bg-primary" />}
      <SidebarMenuButton
        asChild
        isActive={active}
        tooltip={label}
        className="text-muted-foreground hover:bg-overlay-hover hover:text-foreground active:bg-overlay-selected active:text-foreground data-[active=true]:bg-transparent data-[active=true]:text-foreground data-[active=true]:hover:bg-overlay-hover"
      >
        <NavLink to={item.to} aria-current={active ? 'page' : undefined}>
          <item.icon />
          <span>{label}</span>
          {live && <LiveBadge />}
        </NavLink>
      </SidebarMenuButton>
    </SidebarMenuItem>
  );
}

function RailMenu({ items, current, liveSessions = false }: { items: RailItem[]; current: RailPath | null; liveSessions?: boolean }) {
  return (
    <SidebarMenu>
      {items.map((item) => (
        <RailLink key={item.to} item={item} active={current === item.to} live={liveSessions && item.to === '/sessions'} />
      ))}
    </SidebarMenu>
  );
}

function CollapseButton() {
  const { open, toggleSidebar } = useSidebar();
  const Icon = open ? PanelLeftClose : PanelLeftOpen;
  const label = open ? 'Collapse sidebar' : 'Expand sidebar';
  return (
    <button
      type="button"
      onClick={toggleSidebar}
      aria-label={label}
      title={`${label} (Ctrl/Cmd+B)`}
      aria-expanded={open}
      className="flex size-7 shrink-0 items-center justify-center rounded-control text-muted-foreground outline-none hover:bg-overlay-hover hover:text-foreground focus-visible:ring-2 focus-visible:ring-sidebar-ring"
    >
      <Icon className="size-4" />
    </button>
  );
}

export default function AppSidebar() {
  const { pathname } = useLocation();
  const current = railPathFor(pathname);
  const { activeWorkspaceId } = useWorkspace();
  const live = useSessionsLive(activeWorkspaceId)?.live ?? false;

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="flex-row items-center justify-between gap-1 py-2 group-data-[collapsible=icon]:flex-col group-data-[collapsible=icon]:px-2">
        <NavLink
          to="/"
          aria-label="Open Holdem Manager home"
          className="flex h-7 items-center gap-2 rounded-control px-1 text-lg font-bold text-primary outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring"
        >
          <span className="text-xl leading-none">♠</span>
          <span className="group-data-[collapsible=icon]:hidden">OHM</span>
        </NavLink>
        <CollapseButton />
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <RailMenu items={mainItems} current={current} liveSessions={live} />
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup className="mt-auto">
          <SidebarSeparator className="mx-0 mb-2 hidden group-data-[collapsible=icon]:block" />
          <SidebarGroupLabel className="text-label text-subtle-foreground">OHM Extras</SidebarGroupLabel>
          <SidebarGroupContent>
            <RailMenu items={extraItems} current={current} />
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border">
        <RailMenu items={systemItems} current={current} />
      </SidebarFooter>
    </Sidebar>
  );
}
