// Mock API interceptor must be imported first, before any React code
import './mock/api-interceptor';

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { HashRouter, Routes, Route } from 'react-router-dom';
import './index.css';
import LandingApp from './LandingApp';
import SharedHandPage from './components/SharedHandPage';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <HashRouter>
      <Routes>
        <Route path="/" element={<LandingApp />} />
        <Route path="/hand" element={<SharedHandPage />} />
        <Route path="*" element={<LandingApp />} />
      </Routes>
    </HashRouter>
  </StrictMode>,
);
