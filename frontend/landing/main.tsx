// Mock API interceptor must be imported first, before any React code
import './mock/api-interceptor';

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import './index.css';
import LandingApp from './LandingApp';
import SharedHandPage from './components/SharedHandPage';

// LandingApp's showcase components use their own MemoryRouters internally
// (for real page components that need useSearchParams), so LandingApp
// cannot be inside another Router. Only SharedHandPage needs BrowserRouter.
function App() {
  const isHandRoute = window.location.pathname === '/hand';

  if (isHandRoute) {
    return (
      <BrowserRouter>
        <Routes>
          <Route path="/hand" element={<SharedHandPage />} />
          <Route path="*" element={<SharedHandPage />} />
        </Routes>
      </BrowserRouter>
    );
  }

  return <LandingApp />;
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
