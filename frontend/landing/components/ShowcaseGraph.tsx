import { MemoryRouter, Routes, Route } from 'react-router-dom';
import GraphPage from '@/pages/GraphPage';

export default function ShowcaseGraph() {
  return (
    <div className="rounded-xl border border-border overflow-hidden bg-background">
      <MemoryRouter initialEntries={['/graph']}>
        <Routes>
          <Route path="*" element={
            <div className="px-2 py-3">
              <GraphPage />
            </div>
          } />
        </Routes>
      </MemoryRouter>
    </div>
  );
}
