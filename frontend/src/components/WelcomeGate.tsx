import type { ReactNode } from 'react';

// Stub: replaced in M2. Renders the welcome view instead of children while the
// active workspace has no hands (Reports, Statistics, Sessions).
export default function WelcomeGate({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
