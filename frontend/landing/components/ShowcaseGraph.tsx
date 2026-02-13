import { MemoryRouter, Routes, Route } from 'react-router-dom';
import GraphPage from '@/pages/GraphPage';

export default function ShowcaseGraph() {
  return (
    <div className="rounded-xl border border-border overflow-hidden bg-background">
      <MemoryRouter initialEntries={['/graph']}>
        <Routes>
          <Route path="*" element={
            <div className="p-4">
              <GraphPage />
            </div>
          } />
        </Routes>
      </MemoryRouter>
    </div>
  );
}
