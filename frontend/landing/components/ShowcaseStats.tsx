import { MemoryRouter, Routes, Route } from 'react-router-dom';
import StatsPage from '@/pages/StatsPage';

export default function ShowcaseStats() {
  return (
    <div className="rounded-xl border border-border overflow-hidden bg-background">
      <MemoryRouter initialEntries={['/extras/stats']}>
        <Routes>
          <Route path="/extras/stats/:statKey" element={
            <div className="px-2 py-3">
              <StatsPage />
            </div>
          } />
          <Route path="*" element={
            <div className="px-2 py-3">
              <StatsPage />
            </div>
          } />
        </Routes>
      </MemoryRouter>
    </div>
  );
}
