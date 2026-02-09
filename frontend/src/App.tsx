import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { SidebarProvider, SidebarInset, SidebarTrigger } from '@/components/ui/sidebar';
import AppSidebar from '@/components/AppSidebar';
import UploadPage from './pages/UploadPage';
import StatsPage from './pages/StatsPage';
import GraphPage from './pages/GraphPage';
import HandsPage from './pages/HandsPage';
import RangePage from './pages/RangePage';
import CashDropPage from './pages/CashDropPage';

export default function App() {
  return (
    <BrowserRouter>
      <SidebarProvider>
        <AppSidebar />
        <SidebarInset>
          <header className="flex h-10 items-center gap-2 border-b border-border px-4">
            <SidebarTrigger className="-ml-1" />
          </header>
          <main className="flex-1 p-6">
            <Routes>
              <Route path="/" element={<UploadPage />} />
              <Route path="/stats" element={<StatsPage />} />
              <Route path="/graph" element={<GraphPage />} />
              <Route path="/range" element={<RangePage />} />
              <Route path="/hands" element={<HandsPage />} />
              <Route path="/cash-drop" element={<CashDropPage />} />
            </Routes>
          </main>
        </SidebarInset>
      </SidebarProvider>
    </BrowserRouter>
  );
}
