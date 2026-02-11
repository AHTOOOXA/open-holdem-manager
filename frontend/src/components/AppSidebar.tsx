import { BarChart3, Grid3X3, TrendingUp, List, DollarSign, FolderUp, Clock } from 'lucide-react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
} from '@/components/ui/sidebar';
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover';
import ImportPopover from '@/components/ImportPopover';
import SidebarFooterSettings from '@/components/SidebarFooterSettings';
import { useImport } from '@/contexts/ImportContext';

const navItems = [
  { to: '/stats', label: 'Stats', icon: BarChart3 },
  { to: '/range', label: 'Range', icon: Grid3X3 },
  { to: '/graph', label: 'Results', icon: TrendingUp },
  { to: '/sessions', label: 'Sessions', icon: Clock },
  { to: '/hands', label: 'Hands', icon: List },
  { to: '/cash-drop', label: 'Cash Drop', icon: DollarSign },
];

export default function AppSidebar() {
  const location = useLocation();
  const { importPopoverOpen: importOpen, setImportPopoverOpen: setImportOpen } = useImport();

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="px-3 py-4 group-data-[collapsible=icon]:px-1.5">
        <NavLink to="/graph" className="flex items-center gap-2 text-primary font-bold text-lg group-data-[collapsible=icon]:justify-center">
          <span className="text-xl leading-none">♠</span>
          <span className="group-data-[collapsible=icon]:hidden">OHM</span>
        </NavLink>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <Popover open={importOpen} onOpenChange={setImportOpen}>
                  <PopoverTrigger asChild>
                    <SidebarMenuButton tooltip="Import">
                      <FolderUp />
                      <span>Import</span>
                    </SidebarMenuButton>
                  </PopoverTrigger>
                  <PopoverContent side="right" align="start" className="!w-64 p-3">
                    <ImportPopover onClose={() => setImportOpen(false)} />
                  </PopoverContent>
                </Popover>
              </SidebarMenuItem>
              <SidebarSeparator className="my-1" />
              {navItems.map((item) => {
                const isActive = location.pathname.startsWith(item.to);
                return (
                  <SidebarMenuItem key={item.to}>
                    <SidebarMenuButton asChild isActive={isActive} tooltip={item.label}>
                      <NavLink to={item.to}>
                        <item.icon />
                        <span>{item.label}</span>
                      </NavLink>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooterSettings />
    </Sidebar>
  );
}
