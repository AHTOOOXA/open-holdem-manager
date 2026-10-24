import { Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import TagSwatchPicker from '@/components/marked/TagSwatchPicker';
import { getNextMarkerId } from '@/lib/config/api';
import { newColorMarker, patchMarker } from '@/lib/config/logic';
import type { ColorMarker, ColorMarkersConfig } from '@/lib/config/types';
import InlineName from './InlineName';
import SectionHeader from './SectionHeader';
import { ConfigError, ConfigLoading } from './ConfigState';
import { useConfigSection } from './useConfigSection';

export default function ColorMarkersSection() {
  const { env, isError, error, update, reset } = useConfigSection<ColorMarkersConfig>('color_markers', { invalidateAll: true });
  if (isError) return <ConfigError error={error} />;
  if (!env) return <ConfigLoading />;
  const markers = env.value;
  const add = async () => {
    try {
      const { id } = await getNextMarkerId();
      update((cur) => [...cur, newColorMarker(id)]);
    } catch (e) {
      toast.error('Could not add a marker', { description: e instanceof Error ? e.message : undefined });
    }
  };
  const patch = (id: number, p: Partial<ColorMarker>) => update((cur) => patchMarker(cur, id, p));

  return (
    <div>
      <SectionHeader
        title="Color Markers"
        caption="Colours that classify players. A regular gets the first marker flagged as regular, everyone else the first that is not. You can also mark a player by hand."
        onReset={reset}
        resetDescription="The marker list goes back to Fish and Reg."
      />
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead className="w-36">Colour</TableHead>
            <TableHead className="w-24">Is regular</TableHead>
            <TableHead className="w-12"><span className="sr-only">Actions</span></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {markers.map((m) => (
            <TableRow key={m.id} className="group">
              <TableCell>
                <InlineName
                  value={m.name}
                  label={`Name of marker ${m.name}`}
                  onSave={(name) => patch(m.id, { name })}
                  onReject={() => toast.error('A marker needs a name')}
                />
              </TableCell>
              <TableCell>
                <TagSwatchPicker value={m.color} label={`Colour of ${m.name}`} onChange={(color) => patch(m.id, { color })} />
              </TableCell>
              <TableCell>
                <Switch checked={m.is_regular} aria-label={`${m.name} is regular`} onCheckedChange={(is_regular) => patch(m.id, { is_regular })} />
              </TableCell>
              <TableCell>
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-7 opacity-0 group-focus-within:opacity-100 group-hover:opacity-100"
                  aria-label={`Delete marker ${m.name}`}
                  onClick={() => update((cur) => cur.filter((x) => x.id !== m.id))}
                >
                  <Trash2 className="size-3.5" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
          {markers.length === 0 && (
            <TableRow>
              <TableCell colSpan={4} className="text-muted-foreground">No markers.</TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
      <Button variant="outline" size="sm" className="mt-3" onClick={() => void add()}>
        <Plus className="size-3.5" />
        Add color marker…
      </Button>
    </div>
  );
}
