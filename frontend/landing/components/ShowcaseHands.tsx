import { MemoryRouter, Routes, Route } from 'react-router-dom';
import HandExplorer from '@/components/hands/HandExplorer';

export default function ShowcaseHands() {
  return (
    <div className="rounded-xl border border-border overflow-hidden bg-background">
      <MemoryRouter initialEntries={['/hands']}>
        <Routes>
          <Route path="*" element={
            <div className="p-4">
              <HandExplorer defaultPerPage={10} />
            </div>
          } />
        </Routes>
      </MemoryRouter>
    </div>
  );
}
