import { Upload, BarChart3, Grid3X3, TrendingUp, List, DollarSign } from 'lucide-react';
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
} from '@/components/ui/sidebar';

const navItems = [
  { to: '/', label: 'Upload', icon: Upload },
  { to: '/stats', label: 'Stats', icon: BarChart3 },
  { to: '/range', label: 'Range', icon: Grid3X3 },
  { to: '/graph', label: 'Results', icon: TrendingUp },
  { to: '/hands', label: 'Hands', icon: List },
  { to: '/cash-drop', label: 'Cash Drop', icon: DollarSign },
];

export default function AppSidebar() {
  const location = useLocation();

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="px-3 py-4 group-data-[collapsible=icon]:px-1.5">
        <NavLink to="/" className="flex items-center gap-2 text-primary font-bold text-lg group-data-[collapsible=icon]:justify-center">
          <span className="text-xl leading-none">♠</span>
          <span className="group-data-[collapsible=icon]:hidden">OHM</span>
        </NavLink>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => {
                const isActive = item.to === '/'
                  ? location.pathname === '/'
                  : location.pathname.startsWith(item.to);
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
    </Sidebar>
  );
}
