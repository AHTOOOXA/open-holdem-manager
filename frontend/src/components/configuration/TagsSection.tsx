import { useRef, useState } from 'react';
import { ArrowDown, ArrowUp, Pencil, Plus, Trash2 } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import TagSwatchPicker from '@/components/marked/TagSwatchPicker';
import ConfirmDialog from '@/components/databases/ConfirmDialog';
import {
  createTagDef, deleteTagDef, getTagDefs, moveTagDef, resetTagDefs, tagDefsQueryKey, updateTagDef,
} from '@/lib/marked/api';
import type { TagDef } from '@/lib/marked/types';
import InlineName from './InlineName';
import SectionHeader from './SectionHeader';
import { ConfigError, ConfigLoading } from './ConfigState';

function TagRow({ tag, first, last, onUpdate, onMove, onDelete }: {
  tag: TagDef;
  first: boolean;
  last: boolean;
  onUpdate: (patch: Partial<Pick<TagDef, 'name' | 'color'>>) => void;
  onMove: (d: 'up' | 'down') => void;
  onDelete: () => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const act = 'size-7';
  return (
    <TableRow className="group">
      <TableCell>
        <InlineName inputRef={input} value={tag.name} label={`Name of tag ${tag.name}`} onSave={(name) => onUpdate({ name })} onReject={() => toast.error('A tag needs a name')} />
      </TableCell>
      <TableCell>
        <TagSwatchPicker value={tag.color} label={`Colour of ${tag.name}`} onChange={(color) => onUpdate({ color })} />
      </TableCell>
      <TableCell>
        <div className="flex items-center justify-end gap-0.5 opacity-0 group-focus-within:opacity-100 group-hover:opacity-100">
          <Button variant="ghost" size="icon" className={act} disabled={first} aria-label={`Move ${tag.name} up`} onClick={() => onMove('up')}><ArrowUp className="size-3.5" /></Button>
          <Button variant="ghost" size="icon" className={act} disabled={last} aria-label={`Move ${tag.name} down`} onClick={() => onMove('down')}><ArrowDown className="size-3.5" /></Button>
          <Button variant="ghost" size="icon" className={act} aria-label={`Edit ${tag.name}`} onClick={() => input.current?.select()}><Pencil className="size-3.5" /></Button>
          <Button variant="ghost" size="icon" className={act} aria-label={`Delete ${tag.name}`} onClick={onDelete}><Trash2 className="size-3.5" /></Button>
        </div>
      </TableCell>
    </TableRow>
  );
}

export default function TagsSection() {
  const qc = useQueryClient();
  const { data, isError, error } = useQuery({ queryKey: tagDefsQueryKey, queryFn: getTagDefs });
  const [deleting, setDeleting] = useState<TagDef | null>(null);

  const refreshLists = () => {
    // hand lists carry tag chips and filters
    void qc.invalidateQueries({ queryKey: ['hands'] });
    void qc.invalidateQueries({ queryKey: ['general', 'hands'] });
  };
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: tagDefsQueryKey });
    refreshLists();
  };
  const fail = (title: string) => (e: Error) => {
    toast.error(title, { description: e.message });
    refresh();
  };
  const create = useMutation({ mutationFn: () => createTagDef({}), onSuccess: refresh, onError: fail('Could not create the tag') });
  const update = useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: Partial<Pick<TagDef, 'name' | 'color'>> }) => updateTagDef(id, patch),
    onSuccess: refresh,
    onError: fail('Could not save the tag'),
  });
  const move = useMutation({
    mutationFn: ({ id, d }: { id: number; d: 'up' | 'down' }) => moveTagDef(id, d),
    onSuccess: (list) => {
      qc.setQueryData(tagDefsQueryKey, list);
      refreshLists();
    },
    onError: fail('Could not move the tag'),
  });
  const remove = useMutation({
    mutationFn: (id: number) => deleteTagDef(id),
    // Marked hands lose the tag
    onSuccess: () => void qc.invalidateQueries(),
    onError: fail('Could not delete the tag'),
  });
  const reset = useMutation({
    mutationFn: resetTagDefs,
    onSuccess: (list) => {
      qc.setQueryData(tagDefsQueryKey, list);
      void qc.invalidateQueries();
    },
  });

  if (isError) return <ConfigError error={error} />;
  if (!data) return <ConfigLoading />;

  return (
    <div>
      <SectionHeader
        title="Marked Hand Tags"
        caption="Tags help you organise marked hands for review."
        onReset={() => reset.mutateAsync()}
        resetDescription="The tag list goes back to the defaults. Tags that are not in the defaults are removed from the hands that carry them."
      />
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead className="w-36">Colour</TableHead>
            <TableHead className="w-44"><span className="sr-only">Actions</span></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((t, i) => (
            <TagRow
              key={t.id}
              tag={t}
              first={i === 0}
              last={i === data.length - 1}
              onUpdate={(patch) => update.mutate({ id: t.id, patch })}
              onMove={(d) => move.mutate({ id: t.id, d })}
              onDelete={() => setDeleting(t)}
            />
          ))}
          {data.length === 0 && (
            <TableRow>
              <TableCell colSpan={3} className="text-muted-foreground">No tags yet.</TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
      <Button variant="outline" size="sm" className="mt-3" disabled={create.isPending} onClick={() => create.mutate()}>
        <Plus className="size-3.5" />
        Create Tag…
      </Button>
      <ConfirmDialog
        open={deleting !== null}
        title={`Delete the tag "${deleting?.name ?? ''}"?`}
        description="It is removed from every marked hand. The hands stay marked."
        confirmLabel="Delete"
        destructive
        onConfirm={() => {
          if (deleting) remove.mutate(deleting.id);
          setDeleting(null);
        }}
        onCancel={() => setDeleting(null)}
      />
    </div>
  );
}
