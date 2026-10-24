import { useState } from 'react';
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useImport } from '@/contexts/ImportContext';
import { SOFTWARE_OPTIONS, type ImportSoftware } from '@/lib/import/tracker';
import H2NSource from './H2NSource';
import TrackerSource from './TrackerSource';

/** "Import From Database…": pick the tracker, then its database; the date range comes next. */
export default function ImportFromDatabaseDialog() {
  const { showDatabaseImport, setShowDatabaseImport, requestImport } = useImport();
  const [software, setSoftware] = useState<ImportSoftware>('h2n4');

  return (
    <Dialog open={showDatabaseImport} onOpenChange={setShowDatabaseImport}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Import From Database</DialogTitle>
          <DialogDescription>Bring in the hands of another tracker. Cash games only.</DialogDescription>
        </DialogHeader>
        <label className="flex flex-col gap-1.5 text-sm text-muted-foreground">
          Software
          <Select value={software} onValueChange={(v) => setSoftware(v as ImportSoftware)}>
            <SelectTrigger className="w-full" aria-label="Software">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SOFTWARE_OPTIONS.map((o) => (
                <SelectItem key={o.id} value={o.id}>{o.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </label>
        {software === 'h2n4' ? (
          <H2NSource onImport={(path, name) => requestImport({ kind: 'h2n', path, name })} />
        ) : (
          <TrackerSource key={software} software={software} onImport={requestImport} />
        )}
      </DialogContent>
    </Dialog>
  );
}
