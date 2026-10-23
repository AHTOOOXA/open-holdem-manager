import { useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';
import { createWorkspace, updateWorkspace, getSites } from '@/lib/api';
import type { Workspace } from '@/contexts/WorkspaceContext';
import HeroAccountsSection from '@/components/HeroAccountsSection';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import { PRESET_COLORS } from './workspace-colors';

interface Props {
  /** null = create a new workspace */
  workspace: Workspace | null;
  onClose: () => void;
  onSaved: () => Promise<void>;
}

/** Create / edit dialog. Mount it only while open (`key` per workspace) so its fields start fresh. */
export default function WorkspaceFormDialog({ workspace, onClose, onSaved }: Props) {
  const isCreating = workspace === null;
  const [name, setName] = useState(workspace?.name ?? '');
  const [hero, setHero] = useState('');
  const [heroSite, setHeroSite] = useState('');
  const [desc, setDesc] = useState(workspace?.description ?? '');
  const [color, setColor] = useState<string | null>(workspace?.color ?? null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const busyRef = useRef(false);
  const sitesQuery = useQuery({ queryKey: ['sites'], queryFn: getSites, staleTime: Infinity });
  const sites = sitesQuery.data ?? [];
  // A nickname needs its site, otherwise the backend has nothing to attach it to
  const heroMissingSite = isCreating && hero.trim() !== '' && !heroSite;

  const save = async () => {
    if (!name.trim() || heroMissingSite || busyRef.current) return;
    busyRef.current = true;
    setSaving(true);
    setError(null);
    try {
      if (workspace) {
        await updateWorkspace(workspace.id, {
          name: name.trim(),
          description: desc.trim() || undefined,
          color: color ?? undefined,
        });
      } else {
        await createWorkspace({
          name: name.trim(),
          ...(hero.trim() ? { hero_username: hero.trim(), ...(heroSite ? { hero_site: heroSite } : {}) } : {}),
          description: desc.trim() || undefined,
          color: color ?? undefined,
        });
      }
      await onSaved();
      onClose();
    } catch (e) {
      const msg = e instanceof Error && e.message ? e.message : 'Could not save the workspace';
      setError(msg);
      toast.error(isCreating ? 'Create failed' : 'Save failed', { description: msg });
    } finally {
      busyRef.current = false;
      setSaving(false);
    }
  };

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className={isCreating ? 'sm:max-w-md' : 'sm:max-w-xl'}>
        <DialogHeader>
          <DialogTitle>{isCreating ? 'Create workspace' : 'Edit workspace'}</DialogTitle>
          <DialogDescription>
            {isCreating ? 'A workspace keeps its own hands and stats.' : 'Update this workspace.'}
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium">Name</label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
              onKeyDown={(e) => { if (e.key === 'Enter') void save(); }}
            />
          </div>
          {isCreating ? (
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">
                Hero nickname <span className="text-muted-foreground font-normal">(optional)</span>
              </label>
              <div className="flex gap-2">
                <Select value={heroSite} onValueChange={setHeroSite}>
                  <SelectTrigger aria-label="Site" className="w-40 shrink-0">
                    <SelectValue placeholder="Site" />
                  </SelectTrigger>
                  <SelectContent>
                    {sites.map((s) => (
                      <SelectItem key={s.code} value={s.code}>{s.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Input value={hero} onChange={(e) => setHero(e.target.value)} placeholder="Nickname" aria-label="Nickname" />
              </div>
              {heroMissingSite && <p className="text-xs text-muted-foreground">Pick the site this nickname plays on.</p>}
            </div>
          ) : (
            <HeroAccountsSection workspaceId={workspace.id} workspaceName={workspace.name} />
          )}
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium">
              Description <span className="text-muted-foreground font-normal">(optional)</span>
            </label>
            <Textarea value={desc} onChange={(e) => setDesc(e.target.value)} rows={2} />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium">Colour</label>
            <div className="flex items-center gap-1.5">
              {PRESET_COLORS.map((c) => (
                <button
                  key={c.label}
                  type="button"
                  onClick={() => setColor(c.value)}
                  aria-pressed={color === c.value}
                  className={cn(
                    'size-6 rounded-pill border-2 transition-colors',
                    color === c.value ? 'border-foreground ring-1 ring-primary' : 'border-transparent hover:border-muted-foreground/40',
                  )}
                  style={{ backgroundColor: c.value ?? 'var(--subtle-foreground)' }}
                  title={c.label}
                />
              ))}
            </div>
          </div>
          {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={saving}>Cancel</Button>
          <Button onClick={save} disabled={!name.trim() || heroMissingSite || saving}>
            {saving ? (isCreating ? 'Creating...' : 'Saving...') : (isCreating ? 'Create' : 'Save')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
