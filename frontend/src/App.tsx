import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import UploadPage from './pages/UploadPage';
import StatsPage from './pages/StatsPage';
import GraphPage from './pages/GraphPage';
import HandsPage from './pages/HandsPage';
import RangePage from './pages/RangePage';

const navItems = [
  { to: '/', label: 'Upload' },
  { to: '/stats', label: 'Stats' },
  { to: '/range', label: 'Range' },
  { to: '/graph', label: 'Results' },
  { to: '/hands', label: 'Hands' },
];

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen flex flex-col">
        <nav className="border-b border-border bg-surface px-6 py-3 flex items-center gap-6">
          <span className="text-lg font-bold text-primary">OHM</span>
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `text-sm font-medium transition-colors ${
                  isActive ? 'text-primary' : 'text-text-muted hover:text-text'
                }`
              }
              end={item.to === '/'}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <main className="flex-1 p-6">
          <Routes>
            <Route path="/" element={<UploadPage />} />
            <Route path="/stats" element={<StatsPage />} />
            <Route path="/graph" element={<GraphPage />} />
            <Route path="/range" element={<RangePage />} />
            <Route path="/hands" element={<HandsPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
