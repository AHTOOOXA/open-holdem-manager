import { MemoryRouter, Routes, Route } from 'react-router-dom';
import HandExplorer from '@/components/hands/HandExplorer';

export default function ShowcaseHands() {
  return (
    <div className="rounded-xl border border-border overflow-x-auto bg-background">
      <MemoryRouter initialEntries={['/hands']}>
        <Routes>
          <Route path="*" element={
            <div className="px-2 py-3 min-w-[1100px]">
              <HandExplorer defaultPerPage={10} />
            </div>
          } />
        </Routes>
      </MemoryRouter>
    </div>
  );
}
