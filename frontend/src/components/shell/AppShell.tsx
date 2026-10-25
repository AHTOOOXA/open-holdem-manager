import { useCallback, useState, type ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar';
import AppSidebar from '@/components/AppSidebar';
import DbRecoveryBanner from '@/components/DbRecoveryBanner';
import RebuildBanner from '@/components/RebuildBanner';
import { RAIL_LABELS, railPathFor } from '@/lib/routes';
import AppMenuBar from './AppMenuBar';
import StatusBar from './StatusBar';
import NewHandsIndicator from './NewHandsIndicator';
import { useStatAppearanceSync } from './useStatAppearanceSync';
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
  // Number formatting rules: loaded here, formatting components re-render on change (useStatAppearanceVersion)
  useStatAppearanceSync();

  return (
    <SidebarProvider open={open} onOpenChange={setOpen}>
      <LastRouteTracker />
      <AppSidebar />
      {/* min-w-0: wide content (page chains) scrolls inside the column instead of widening the window */}
      <SidebarInset className="min-w-0">
        <header className="flex h-(--shell-header-h) shrink-0 items-center gap-1 border-b border-border px-2">
          <AppMenuBar />
          <div className="ml-auto flex min-w-0 items-center gap-3 pl-3">
            <NewHandsIndicator />
            {rail && (
              <span className="truncate text-xs text-subtle-foreground">
                {RAIL_LABELS[rail]}
              </span>
            )}
          </div>
        </header>
        <DbRecoveryBanner />
        <RebuildBanner />
        <div className="flex-1 p-4">{children}</div>
        <StatusBar />
      </SidebarInset>
    </SidebarProvider>
  );
}
