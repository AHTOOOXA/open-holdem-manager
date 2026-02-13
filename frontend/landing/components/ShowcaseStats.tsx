import { MemoryRouter, Routes, Route } from 'react-router-dom';
import StatsPage from '@/pages/StatsPage';

export default function ShowcaseStats() {
  return (
    <div className="rounded-xl border border-border overflow-hidden bg-background">
      <MemoryRouter initialEntries={['/stats']}>
        <Routes>
          <Route path="/stats/:statKey" element={
            <div className="p-4">
              <StatsPage />
            </div>
          } />
          <Route path="*" element={
            <div className="p-4">
              <StatsPage />
            </div>
          } />
        </Routes>
      </MemoryRouter>
    </div>
  );
}
