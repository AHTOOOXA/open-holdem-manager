import { useSyncExternalStore } from 'react';
import { getStatAppearanceVersion, subscribeStatAppearance } from './h2n';

/**
 * Subscribe a component that formats stats to Configuration > Stat Appearance: it re-renders (no
 * remount) when the formatting rules change. Call it at the top of every component that calls the
 * H2N formatters.
 */
export function useStatAppearanceVersion(): number {
  return useSyncExternalStore(subscribeStatAppearance, getStatAppearanceVersion);
}
