import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '@/lib/query-client';
import { SidebarProvider, SidebarInset, SidebarTrigger } from '@/components/ui/sidebar';
import { ImportProvider } from '@/contexts/ImportContext';
import ImportOverlay from '@/components/ImportOverlay';
import AppSidebar from '@/components/AppSidebar';
import StatsPage from './pages/StatsPage';
import GraphPage from './pages/GraphPage';
import HandsPage from './pages/HandsPage';
import RangePage from './pages/RangePage';
import CashDropPage from './pages/CashDropPage';

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
    <BrowserRouter>
      <ImportProvider>
        <SidebarProvider>
          <AppSidebar />
          <SidebarInset>
            <header className="flex h-10 items-center gap-2 border-b border-border px-4">
              <SidebarTrigger className="-ml-1" />
            </header>
            <main className="flex-1 p-4">
              <Routes>
                <Route path="/" element={<Navigate to="/graph" replace />} />
                <Route path="/stats" element={<StatsPage />} />
                <Route path="/graph" element={<GraphPage />} />
                <Route path="/range" element={<RangePage />} />
                <Route path="/hands" element={<HandsPage />} />
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
