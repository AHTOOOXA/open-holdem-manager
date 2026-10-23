import { useCallback, useState, type ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import { SidebarInset, SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar';
import { Separator } from '@/components/ui/separator';
import AppSidebar from '@/components/AppSidebar';
import DbRecoveryBanner from '@/components/DbRecoveryBanner';
import { RAIL_LABELS, railPathFor } from '@/lib/routes';
import AppMenuBar from './AppMenuBar';
import StatusBar from './StatusBar';
import { LastRouteTracker } from './Redirects';

const SIDEBAR_OPEN_KEY = 'ohm.sidebarOpen';

function readSidebarOpen(): boolean {
  try {
    return localStorage.getItem(SIDEBAR_OPEN_KEY) === 'true';
  } catch {
    return false;
  }
}

/**
 * The app frame: icon rail on the left; on the right a caption row (sidebar toggle, menus,
 * screen title), the screen, and the status bar.
 */
export default function AppShell({ children }: { children: ReactNode }) {
  // Collapsed (icons only) unless the user expanded it last time
  const [open, setOpenState] = useState(readSidebarOpen);
  const setOpen = useCallback((value: boolean) => {
    setOpenState(value);
    try {
      localStorage.setItem(SIDEBAR_OPEN_KEY, String(value));
    } catch {
      // localStorage unavailable
    }
  }, []);

  const { pathname } = useLocation();
  const rail = railPathFor(pathname);

  return (
    <SidebarProvider open={open} onOpenChange={setOpen}>
      <LastRouteTracker />
      <AppSidebar />
      <SidebarInset>
        <header className="flex h-(--shell-header-h) shrink-0 items-center gap-1 border-b border-border px-2">
          <SidebarTrigger className="text-muted-foreground hover:bg-overlay-hover hover:text-foreground" />
          <Separator orientation="vertical" className="mx-1 data-[orientation=vertical]:h-4" />
          <AppMenuBar />
          {rail && (
            <span className="ml-auto truncate pl-3 text-xs text-subtle-foreground">
              {RAIL_LABELS[rail]}
            </span>
          )}
        </header>
        <DbRecoveryBanner />
        <div className="flex-1 p-4">{children}</div>
        <StatusBar />
      </SidebarInset>
    </SidebarProvider>
  );
}
