import { useWorkspace } from '@/contexts/WorkspaceContext';
import HeroAccountsSection from '@/components/HeroAccountsSection';

export default function HeroNicknamesSection() {
  const { activeWorkspace } = useWorkspace();
  if (!activeWorkspace) return <p className="text-sm text-muted-foreground">No workspace selected.</p>;
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        Your accounts in the '{activeWorkspace.name}' workspace. OHM detects them on import; add nicknames to override.
      </p>
      <HeroAccountsSection key={activeWorkspace.id} workspaceId={activeWorkspace.id} workspaceName={activeWorkspace.name} />
    </div>
  );
}
