import { BrowserRouter, Routes, Route, Navigate, useLocation, Link } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '@/lib/query-client';
import { SidebarProvider, SidebarInset, SidebarTrigger } from '@/components/ui/sidebar';
import { Separator } from '@/components/ui/separator';
import {
  Breadcrumb,
  BreadcrumbList,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb';
import { ImportProvider } from '@/contexts/ImportContext';
import ImportOverlay from '@/components/ImportOverlay';
import AppSidebar from '@/components/AppSidebar';
import { getStatDisplayName } from '@/lib/stat-registry';
import StatsPage from './pages/StatsPage';
import GraphPage from './pages/GraphPage';
import HandsPage from './pages/HandsPage';
import RangePage from './pages/RangePage';
import CashDropPage from './pages/CashDropPage';
import SessionsPage from './pages/SessionsPage';

const PAGE_LABELS: Record<string, string> = {
  '/stats': 'Stats',
  '/range': 'Range',
  '/graph': 'Results',
  '/sessions': 'Sessions',
  '/hands': 'Hands',
  '/cash-drop': 'Cash Drop',
};

function AppBreadcrumb() {
  const { pathname } = useLocation();

  // Build breadcrumb segments from pathname
  const segments: { label: string; href?: string }[] = [];

  // Find the top-level page
  const topPath = '/' + pathname.split('/').filter(Boolean)[0];
  const topLabel = PAGE_LABELS[topPath];

  if (!topLabel) return null;

  // Check if we have a sub-page (e.g., /sessions/123 or /stats/vpip)
  const parts = pathname.split('/').filter(Boolean);
  if (parts.length > 1 && topPath === '/sessions') {
    segments.push({ label: topLabel, href: topPath });
    segments.push({ label: `Session #${parts[1]}` });
  } else if (parts.length > 1 && topPath === '/stats') {
    segments.push({ label: topLabel, href: topPath });
    segments.push({ label: getStatDisplayName(parts[1]) });
  } else {
    segments.push({ label: topLabel });
  }

  return (
    <Breadcrumb>
      <BreadcrumbList>
        {segments.map((seg, i) => {
          const isLast = i === segments.length - 1;
          return (
            <BreadcrumbItem key={i} className={i === 0 ? '' : ''}>
              {i > 0 && <BreadcrumbSeparator />}
              {isLast ? (
                <BreadcrumbPage>{seg.label}</BreadcrumbPage>
              ) : (
                <BreadcrumbLink asChild>
                  <Link to={seg.href!}>{seg.label}</Link>
                </BreadcrumbLink>
              )}
            </BreadcrumbItem>
          );
        })}
      </BreadcrumbList>
    </Breadcrumb>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
    <BrowserRouter>
      <ImportProvider>
        <SidebarProvider>
          <AppSidebar />
          <SidebarInset>
            <header className="flex h-10 shrink-0 items-center gap-2 border-b border-border px-4">
              <SidebarTrigger className="-ml-1" />
              <Separator orientation="vertical" className="mr-2 data-[orientation=vertical]:h-4" />
              <AppBreadcrumb />
            </header>
            <main className="flex-1 p-4">
              <Routes>
                <Route path="/" element={<Navigate to="/graph" replace />} />
                <Route path="/stats" element={<StatsPage />} />
                <Route path="/stats/:statKey" element={<StatsPage />} />
                <Route path="/graph" element={<GraphPage />} />
                <Route path="/range" element={<RangePage />} />
                <Route path="/hands" element={<HandsPage />} />
                <Route path="/sessions" element={<SessionsPage />} />
                <Route path="/sessions/:sessionIndex" element={<SessionsPage />} />
                <Route path="/cash-drop" element={<CashDropPage />} />
                <Route path="*" element={<Navigate to="/graph" replace />} />
              </Routes>
            </main>
          </SidebarInset>
        </SidebarProvider>
        <ImportOverlay />
      </ImportProvider>
    </BrowserRouter>
    </QueryClientProvider>
  );
}
