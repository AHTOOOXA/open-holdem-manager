import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '@/lib/query-client';
import { DEFAULT_ROUTE, LEGACY_PATHS } from '@/lib/routes';
import { ImportProvider } from '@/contexts/ImportContext';
import { WorkspaceProvider } from '@/contexts/WorkspaceContext';
import ImportOverlay from '@/components/ImportOverlay';
import DragDropOverlay from '@/components/DragDropOverlay';
import WelcomeGate from '@/components/WelcomeGate';
import AppShell from '@/components/shell/AppShell';
import { HomeRedirect, LegacyRedirect } from '@/components/shell/Redirects';
import { Toaster } from '@/components/ui/sonner';
import ReportsPage from './pages/ReportsPage';
import StatisticsPage from './pages/StatisticsPage';
import SessionsPage from './pages/SessionsPage';
import MarkedHandsPage from './pages/MarkedHandsPage';
import DatabasesPage from './pages/DatabasesPage';
import ConfigurationPage from './pages/ConfigurationPage';
import StatsPage from './pages/StatsPage';
import ComparePage from './pages/ComparePage';
import CashDropPage from './pages/CashDropPage';
import PopulationPage from './pages/PopulationPage';
import PlayersPage from './pages/PlayersPage';
import PlayerProfilePage from './pages/PlayerProfilePage';
import IdentityDetailPage from './pages/IdentityDetailPage';
import DesignPage from './pages/DesignPage';
import PageChainDemo from './pages/design/PageChainDemo';
import DataGridDemo from './pages/design/DataGridDemo';

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
    <WorkspaceProvider>
    <BrowserRouter>
      <ImportProvider>
        <AppShell>
          <Routes>
            <Route path="/" element={<HomeRedirect />} />

            {/* Main screens */}
            <Route path="/reports" element={<WelcomeGate><ReportsPage /></WelcomeGate>} />
            <Route path="/statistics" element={<WelcomeGate><StatisticsPage /></WelcomeGate>} />
            <Route path="/sessions" element={<WelcomeGate><SessionsPage /></WelcomeGate>} />
            <Route path="/sessions/:sessionIndex" element={<WelcomeGate><SessionsPage /></WelcomeGate>} />
            <Route path="/marked" element={<MarkedHandsPage />} />

            {/* OHM Extras */}
            <Route path="/extras/stats" element={<StatsPage />} />
            <Route path="/extras/stats/:statKey" element={<StatsPage />} />
            <Route path="/extras/compare" element={<ComparePage />} />
            <Route path="/extras/cash-drop" element={<CashDropPage />} />
            <Route path="/extras/population" element={<PopulationPage />} />
            <Route path="/extras/players" element={<PlayersPage />} />
            <Route path="/extras/players/identity/:identityId" element={<IdentityDetailPage />} />
            <Route path="/extras/players/:playerId" element={<PlayerProfilePage />} />

            {/* System */}
            <Route path="/databases" element={<DatabasesPage />} />
            <Route path="/configuration" element={<ConfigurationPage />} />
            <Route path="/configuration/:section" element={<ConfigurationPage />} />
            <Route path="/design" element={<DesignPage />} />
            <Route path="/design/page-chain" element={<div className="p-4"><PageChainDemo /></div>} />
            <Route path="/design/data-grid" element={<div className="p-4"><DataGridDemo /></div>} />

            {/* Old URLs keep working: /graph -> /reports?tab=graph, /stats/x -> /extras/stats/x ... */}
            {LEGACY_PATHS.map((from) => (
              <Route key={from} path={from} element={<LegacyRedirect from={from} />} />
            ))}

            <Route path="*" element={<Navigate to={DEFAULT_ROUTE} replace />} />
          </Routes>
        </AppShell>
        <ImportOverlay />
        <DragDropOverlay />
        <Toaster position="bottom-right" offset={{ bottom: 40, right: 16 }} />
      </ImportProvider>
    </BrowserRouter>
    </WorkspaceProvider>
    </QueryClientProvider>
  );
}
