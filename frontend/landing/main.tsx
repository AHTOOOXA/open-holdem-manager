// Mock API interceptor must be imported first, before any React code
import './mock/api-interceptor';

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import '@/index.css';
import LandingApp from './LandingApp';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <LandingApp />
  </StrictMode>,
);
