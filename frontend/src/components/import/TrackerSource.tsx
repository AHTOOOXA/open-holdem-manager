import { useEffect, useRef, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { grouped } from '@/lib/format';
import {
  activeConnection, databaseOptionLabel, getTrackerDatabases, loadConnection, saveConnection, searchMessage,
  type ImportSource, type SavedConnection,
} from '@/lib/import/tracker';
import type { TrackerDatabases, TrackerSoftware } from '@/lib/import/types';

const storage = () => (typeof localStorage === 'undefined' ? null : localStorage);

/**
 * PokerTracker 4 / Holdem Manager 3 branch: finds the databases on the server and imports the chosen one.
 * Searches when opened and when "Search" is pressed; editing the settings never sends a request by itself.
 */
export default function TrackerSource({ software, onImport }: {
  software: TrackerSoftware;
  onImport: (source: Extract<ImportSource, { kind: 'tracker' }>) => void;
}) {
  const [conn, setConn] = useState<SavedConnection>(() => loadConnection(storage(), software));
  // Never persisted
  const [password, setPassword] = useState('');
  const [result, setResult] = useState<TrackerDatabases | null>(null);
  const [selected, setSelected] = useState('');
  const [searching, setSearching] = useState(true);
  // Bumped by the Search button; the search effect runs on open, on a software change and on this
  const [searchRun, setSearchRun] = useState(0);
  // Settings edited since the last search: the listed databases may not match them
  const [edited, setEdited] = useState(false);
  // The connection the effect reads; set when a search starts, not on every keystroke
  const connRef = useRef<{ conn: SavedConnection; password: string }>({ conn, password });

  useEffect(() => {
    const ctl = new AbortController();
    const { conn: c, password: pw } = connRef.current;
    getTrackerDatabases(software, activeConnection(c, pw), ctl.signal)
      .then((r) => {
        setResult(r);
        setSelected(r.databases[0]?.name ?? '');
      })
      .catch((e: unknown) => {
        if (ctl.signal.aborted) return;
        setResult({ software, databases: [], error: e instanceof Error ? e.message : 'Search failed' });
        setSelected('');
      })
      .finally(() => {
        if (!ctl.signal.aborted) setSearching(false);
      });
    return () => ctl.abort();
  }, [software, searchRun]);

  const search = () => {
    connRef.current = { conn, password };
    setEdited(false);
    setResult(null);
    setSearching(true);
    setSearchRun((n) => n + 1);
  };

  const edit = (patch: Partial<SavedConnection>) => {
    const next = { ...conn, ...patch };
    setConn(next);
    setEdited(true);
    saveConnection(storage(), software, next);
  };

  const message = searching ? null : searchMessage(result);

  return (
    <div className="flex flex-col gap-3">
      <label className="flex items-center gap-2 text-sm">
        <Checkbox checked={conn.custom} onCheckedChange={(v) => edit({ custom: v === true })} />
        Custom settings
      </label>
      {conn.custom && (
        <div className="grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-2 text-sm">
          <label htmlFor="trk-host" className="text-muted-foreground">Host</label>
          <Input id="trk-host" value={conn.host} placeholder="localhost" onChange={(e) => edit({ host: e.target.value })} autoComplete="off" />
          <label htmlFor="trk-port" className="text-muted-foreground">Port</label>
          <Input id="trk-port" value={conn.port} placeholder="5432" inputMode="numeric" onChange={(e) => edit({ port: e.target.value })} autoComplete="off" />
          <label htmlFor="trk-user" className="text-muted-foreground">Username</label>
          <Input id="trk-user" value={conn.user} placeholder="postgres" onChange={(e) => edit({ user: e.target.value })} autoComplete="off" />
          <label htmlFor="trk-pass" className="text-muted-foreground">Password</label>
          <Input
            id="trk-pass"
            type="password"
            value={password}
            onChange={(e) => { setPassword(e.target.value); setEdited(true); }}
            onKeyDown={(e) => { if (e.key === 'Enter') search(); }}
            autoComplete="off"
          />
        </div>
      )}
      {searching ? (
        <div className="flex h-8 items-center justify-center gap-2 text-sm text-muted-foreground" role="status">
          <Loader2 className="size-4 animate-spin" aria-hidden />
          Looking for databases…
        </div>
      ) : message ? (
        <p role="alert" className="py-1 text-center text-sm text-money-neg">{message}</p>
      ) : result && (
        <label className="flex flex-col gap-1.5 text-sm text-muted-foreground">
          Database
          <Select value={selected} onValueChange={setSelected}>
            <SelectTrigger className="w-full" aria-label="Database">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {result.databases.map((d) => (
                <SelectItem key={d.name} value={d.name}>{databaseOptionLabel(d, grouped)}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </label>
      )}
      <div className="flex justify-end gap-2">
        <Button variant="outline" disabled={searching} onClick={search}>
          Search
        </Button>
        <Button
          disabled={searching || edited || !selected}
          title={edited ? 'Settings changed: press Search first' : undefined}
          onClick={() => onImport({ kind: 'tracker', software, database: selected, conn: activeConnection(conn, password) })}
        >
          Import
        </Button>
      </div>
    </div>
  );
}
