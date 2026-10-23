import { useEffect } from 'react';
import { Navigate, useLocation, useParams } from 'react-router-dom';
import {
  LAST_ROUTE_KEY,
  legacyRedirect,
  railPathFor,
  resolveLastRoute,
  type LegacyPath,
} from '@/lib/routes';

/** Sends an old URL to its new home, keeping params, query and hash. */
export function LegacyRedirect({ from }: { from: LegacyPath }) {
  const params = useParams();
  const { search, hash } = useLocation();
  return <Navigate to={legacyRedirect(from, params, search, hash)} replace />;
}

function readLastRoute(): string | null {
  try {
    return localStorage.getItem(LAST_ROUTE_KEY);
  } catch {
    return null;
  }
}

/** `/` opens the screen the user was on last time (Reports the first time). */
export function HomeRedirect() {
  return <Navigate to={resolveLastRoute(readLastRoute())} replace />;
}

/** Remembers the current rail destination so `/` can return to it. Renders nothing. */
export function LastRouteTracker() {
  const { pathname } = useLocation();
  useEffect(() => {
    const rail = railPathFor(pathname);
    if (!rail) return;
    try {
      localStorage.setItem(LAST_ROUTE_KEY, rail);
    } catch {
      // localStorage unavailable
    }
  }, [pathname]);
  return null;
}
