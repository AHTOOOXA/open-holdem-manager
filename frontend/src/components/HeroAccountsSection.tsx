import { useEffect, useRef, useState } from 'react';
import { Pencil, Plus, Trash2 } from 'lucide-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getHeroes,
  getSites,
  setHeroAutoDetect,
  setManualHeroes,
  type HeroAccount,
  type Site,
} from '@/lib/api';
import {
  firstSiteWithoutManual,
  groupBySite,
  heroSummary,
  normalizeNicknames,
} from '@/lib/hero-accounts';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Card, CardContent } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';

interface Row {
  id: number;
  value: string;
}

interface NicknamesFormProps {
  sites: Site[];
  initialSite: string;
  initialNames: string[];
  saving: boolean;
  onCancel: () => void;
  onSave: (site: string, names: string[]) => void;
}

let nextRowId = 0;
const makeRow = (value: string): Row => ({ id: nextRowId++, value });

function NicknamesForm({ sites, initialSite, initialNames, saving, onCancel, onSave }: NicknamesFormProps) {
  const [site, setSite] = useState(initialSite);
  const [rows, setRows] = useState<Row[]>(() =>
    (initialNames.length ? initialNames : ['']).map(makeRow),
  );
  const firstRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    firstRef.current?.focus();
    firstRef.current?.select();
  }, []);

  const names = normalizeNicknames(rows.map((r) => r.value));

  return (
    <>
      <div className="flex flex-col gap-4">
        <Select value={site} onValueChange={setSite}>
          <SelectTrigger aria-label="Site" className="w-full">
            <SelectValue placeholder="Site" />
          </SelectTrigger>
          <SelectContent>
            {sites.map((s) => (
              <SelectItem key={s.code} value={s.code}>{s.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">Nickname(s):</span>
          <div className="grid grid-cols-2 gap-2">
            {rows.map((row, i) => (
              <div key={row.id} className="flex items-center gap-1">
                <Input
                  ref={i === 0 ? firstRef : undefined}
                  value={row.value}
                  aria-label={`Nickname ${i + 1}`}
                  onChange={(e) =>
                    setRows((rs) => rs.map((r) => (r.id === row.id ? { ...r, value: e.target.value } : r)))
                  }
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && site) onSave(site, names);
                  }}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  aria-label={`Remove nickname ${i + 1}`}
                  onClick={() =>
                    setRows((rs) => (rs.length > 1 ? rs.filter((r) => r.id !== row.id) : [makeRow('')]))
                  }
                >
                  <Trash2 className="size-4" />
                </Button>
              </div>
            ))}
          </div>
          <div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setRows((rs) => [...rs, makeRow('')])}
            >
              <Plus className="size-4" />
              Add nickname
            </Button>
          </div>
        </div>
      </div>
      <DialogFooter>
        <Button variant="outline" onClick={onCancel} disabled={saving}>Cancel</Button>
        <Button onClick={() => onSave(site, names)} disabled={!site || saving}>
          {saving ? 'Saving...' : 'Save'}
        </Button>
      </DialogFooter>
    </>
  );
}

type DialogState = { editSite: string | null } | null;

export default function HeroAccountsSection({ workspaceId, workspaceName }: { workspaceId: number; workspaceName: string }) {
  const queryClient = useQueryClient();
  const [dialog, setDialog] = useState<DialogState>(null);
  const [saving, setSaving] = useState(false);

  const sitesQuery = useQuery({ queryKey: ['sites'], queryFn: getSites, staleTime: Infinity });
  const heroesQuery = useQuery({
    queryKey: ['heroes', workspaceId],
    queryFn: () => getHeroes(workspaceId),
  });

  const sites = sitesQuery.data ?? [];
  const heroes = heroesQuery.data;
  const accounts: HeroAccount[] = heroes?.accounts ?? [];
  const manualGroups = groupBySite(accounts, 'manual');
  const autoGroups = groupBySite(accounts, 'auto');

  // The active hero drives every stat screen, so refresh everything after a change.
  const refresh = () => queryClient.invalidateQueries();

  const saveSite = async (site: string, names: string[]) => {
    const editSite = dialog?.editSite ?? null;
    setSaving(true);
    try {
      if (editSite && editSite !== site) await setManualHeroes(workspaceId, editSite, []);
      await setManualHeroes(workspaceId, site, names);
      await refresh();
      setDialog(null);
    } finally {
      setSaving(false);
    }
  };

  const removeSite = async (site: string) => {
    await setManualHeroes(workspaceId, site, []);
    await refresh();
  };

  const toggleAuto = async (checked: boolean) => {
    await setHeroAutoDetect(workspaceId, checked);
    await refresh();
  };

  const editing = dialog?.editSite ?? null;
  const editingNames = editing
    ? accounts.filter((a) => a.source === 'manual' && a.site === editing).map((a) => a.username)
    : [];

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-medium">Hero accounts</span>
          <p className="text-xs text-text-muted">{heroSummary(heroes?.active ?? null)}</p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="shrink-0"
          disabled={sites.length === 0}
          onClick={() => setDialog({ editSite: null })}
        >
          <Plus className="size-4" />
          Add hero nicknames…
        </Button>
      </div>

      {manualGroups.length > 0 && (
        <div className="grid grid-cols-2 gap-2">
          {manualGroups.map((g) => (
            <Card key={g.site} className="group py-0">
              <CardContent className="flex items-start justify-between gap-2 p-3">
                <div className="min-w-0">
                  <div className="text-sm font-semibold">{g.site_name}</div>
                  {g.accounts.map((a) => (
                    <div key={a.username} className="truncate text-sm">{a.username}</div>
                  ))}
                </div>
                <div className="flex shrink-0 opacity-60 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`Edit ${g.site_name} nicknames`}
                    onClick={() => setDialog({ editSite: g.site })}
                  >
                    <Pencil className="size-4" />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`Delete ${g.site_name} nicknames`}
                    onClick={() => removeSite(g.site)}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <div className="flex flex-col gap-2">
        <span className="text-sm font-medium">Auto detection</span>
        <label className="flex items-center gap-2 text-sm">
          <Switch
            checked={heroes?.auto_detect ?? false}
            disabled={!heroes}
            onCheckedChange={toggleAuto}
          />
          Detect hero nicknames automatically when importing hands
        </label>
        {autoGroups.length > 0 && (
          <>
            <div className="text-sm font-bold">Detected in '{workspaceName}':</div>
            <div className="pointer-events-none grid grid-cols-2 gap-2 opacity-50">
              {autoGroups.map((g) => (
                <Card key={g.site} className="py-0">
                  <CardContent className="p-3">
                    <div className="text-sm font-semibold">{g.site_name}</div>
                    {g.accounts.map((a) => (
                      <div key={a.username} className="flex justify-between gap-2 text-sm">
                        <span className="truncate">{a.username}</span>
                        <span className="shrink-0 text-text-muted">{a.hand_count.toLocaleString()} hands</span>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              ))}
            </div>
          </>
        )}
      </div>

      <Dialog open={dialog !== null} onOpenChange={(open) => { if (!open && !saving) setDialog(null); }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Hero nicknames</DialogTitle>
          </DialogHeader>
          {dialog && (
            <NicknamesForm
              sites={sites}
              initialSite={editing ?? firstSiteWithoutManual(sites, accounts)}
              initialNames={editingNames}
              saving={saving}
              onCancel={() => setDialog(null)}
              onSave={saveSite}
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
