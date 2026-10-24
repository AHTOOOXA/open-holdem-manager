import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { grouped } from '@/lib/format';
import { listH2NDatabases, type H2NDatabase } from '@/lib/api';

interface Props {
  onImport: (path: string, name: string) => void;
}

/** Hand2Note 4 branch of "Import From Database": lists the databases on this machine, or takes a folder path. */
export default function H2NSource({ onImport }: Props) {
  const [databases, setDatabases] = useState<H2NDatabase[] | null>(null);
  const [customPath, setCustomPath] = useState('');

  useEffect(() => {
    listH2NDatabases()
      .then((r) => setDatabases(r.databases))
      .catch(() => setDatabases([]));
  }, []);

  const trimmed = customPath.trim();

  return (
    <div className="flex w-full flex-col gap-3">
      {databases === null ? (
        <p className="text-xs text-text-muted">Looking for Hand2Note databases...</p>
      ) : databases.length > 0 ? (
        <div className="flex flex-col gap-2">
          {databases.map((db) => (
            <div key={db.path} className="flex items-center justify-between gap-4 text-sm">
              <div className="min-w-0">
                <div className="truncate">{db.name}</div>
                <div className="text-xs text-text-muted">{grouped(db.hands)} hands</div>
              </div>
              <Button size="sm" variant="outline" onClick={() => onImport(db.path, db.name)}>
                Import
              </Button>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-text-muted">No Hand2Note databases found in the default folder.</p>
      )}
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (trimmed) onImport(trimmed, trimmed.split(/[\\/]/).filter(Boolean).pop() ?? trimmed);
        }}
      >
        <Input
          value={customPath}
          onChange={(e) => setCustomPath(e.target.value)}
          placeholder="Or paste a database folder path"
          className="h-8 text-xs"
        />
        <Button type="submit" size="sm" variant="outline" disabled={!trimmed}>
          Import
        </Button>
      </form>
      <p className="text-xs text-text-muted">
        Reads the original hand histories Hand2Note 4 keeps for your own databases. Hand2Note doesn't need to be
        running.
      </p>
    </div>
  );
}
