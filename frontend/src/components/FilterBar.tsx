import { useState, useRef, useEffect } from 'react';
import { format } from 'date-fns';
import { PlusIcon } from 'lucide-react';
import type { DatePreset } from '@/lib/date-presets';
import type { FilterOptions } from '@/lib/api';
import { formatStakes } from '@/lib/utils';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { DatePicker } from '@/components/ui/date-picker';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';

const GAME_MODE_LABELS: Record<string, string> = {
  '': 'Regular',
  'Fast Fold': 'Fast Fold',
};

export interface CheckpointItem {
  id: number;
  name: string;
  checkpoint_at: string;
  note: string | null;
}

interface FilterBarProps {
  stakes?: string;
  onStakesChange?: (v: string) => void;
  gameMode?: string;
  onGameModeChange?: (v: string) => void;
  dateFrom?: string;
  onDateFromChange?: (v: string) => void;
  dateTo?: string;
  onDateToChange?: (v: string) => void;
  activePreset?: DatePreset;
  onPresetChange?: (preset: DatePreset) => void;
  showStakes?: boolean;
  showGameMode?: boolean;
  showDateRange?: boolean;
  showDatePresets?: boolean;
  filterOptions: FilterOptions | null;
  children?: React.ReactNode;
  // Checkpoint props
  checkpointId?: string | null;
  onCheckpointChange?: (id: string | null) => void;
  checkpoints?: CheckpointItem[];
  showCheckpoints?: boolean;
  onCreateCheckpoint?: (data: { name: string; checkpoint_at: string; note?: string }) => Promise<void>;
}

function formatCheckpointDate(isoDate: string): string {
  try {
    const d = new Date(isoDate);
    const time = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
    const hasTime = time !== '00:00';
    const dateStr = format(d, 'MMM d');
    return hasTime ? `${dateStr} ${time}` : dateStr;
  } catch {
    return isoDate.slice(0, 10);
  }
}

export default function FilterBar({
  stakes,
  onStakesChange,
  gameMode,
  onGameModeChange,
  dateFrom,
  onDateFromChange,
  dateTo,
  onDateToChange,
  activePreset,
  onPresetChange,
  showStakes = true,
  showGameMode = true,
  showDateRange = true,
  showDatePresets = true,
  filterOptions,
  children,
  checkpointId,
  onCheckpointChange,
  checkpoints,
  showCheckpoints = true,
  onCreateCheckpoint,
}: FilterBarProps) {
  const [newDialogOpen, setNewDialogOpen] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDate, setNewDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [newTime, setNewTime] = useState(() => {
    const now = new Date();
    return `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
  });
  const [newNote, setNewNote] = useState('');
  const [creating, setCreating] = useState(false);
  const nameInputRef = useRef<HTMLInputElement>(null);

  // Focus the name input when dialog opens
  useEffect(() => {
    if (newDialogOpen) {
      // Small delay to let dialog mount
      const t = setTimeout(() => nameInputRef.current?.focus(), 50);
      return () => clearTimeout(t);
    }
  }, [newDialogOpen]);

  const presetBtn = (preset: DatePreset, label: string) => (
    <Button
      key={preset}
      variant={activePreset === preset ? 'default' : 'outline'}
      size="sm"
      className="h-7 text-xs"
      onClick={() => {
        onPresetChange?.(preset);
        // handlePreset in pages already clears checkpointId via setCheckpointId(null).
        // Do NOT call onCheckpointChange here — it would also setDateFrom(''),
        // overriding the preset's dateFrom in the same React batch.
      }}
    >
      {label}
    </Button>
  );

  const hasMultipleModes = filterOptions?.game_modes && filterOptions.game_modes.length > 1;

  // "__all__" means no filter; gameMode prop is "" when not filtering,
  // but "" is also a valid game_mode value (Regular). We use "__all__" as the sentinel.
  const gameModeValue = gameMode === undefined || gameMode === '' ? '__all__' : gameMode;

  // Sort checkpoints by checkpoint_at descending
  const sortedCheckpoints = checkpoints
    ? [...checkpoints].sort((a, b) => b.checkpoint_at.localeCompare(a.checkpoint_at))
    : [];

  const showCheckpointSelect =
    showCheckpoints &&
    onCheckpointChange &&
    (sortedCheckpoints.length > 0 || !!onCreateCheckpoint);

  const checkpointSelectValue = checkpointId || '__all_time__';

  const handleCheckpointChange = (value: string) => {
    if (value === '__new__') {
      // Reset form and open dialog
      const now = new Date();
      setNewName('');
      setNewDate(now.toISOString().slice(0, 10));
      setNewTime(`${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`);
      setNewNote('');
      setNewDialogOpen(true);
      return;
    }
    if (value === '__all_time__') {
      onCheckpointChange?.(null);
    } else {
      onCheckpointChange?.(value);
    }
  };

  const handleCreateCheckpoint = async () => {
    if (!newName.trim() || !onCreateCheckpoint) return;
    setCreating(true);
    try {
      await onCreateCheckpoint({
        name: newName.trim(),
        checkpoint_at: `${newDate}T${newTime || '00:00'}:00`,
        note: newNote.trim() || undefined,
      });
      setNewDialogOpen(false);
    } finally {
      setCreating(false);
    }
  };

  // Build display text for the selected checkpoint
  const selectedCheckpoint = checkpointId
    ? sortedCheckpoints.find((c) => String(c.id) === checkpointId)
    : null;

  return (
    <>
      <Card className="gap-0 py-0">
        <CardContent className="px-3 py-2 flex flex-wrap items-center gap-3">
          {showStakes && filterOptions && filterOptions.stakes.length > 0 && (
            <Select
              value={stakes || '__all__'}
              onValueChange={(v) => onStakesChange?.(v === '__all__' ? '' : v)}
            >
              <SelectTrigger className="w-[130px] h-8 text-sm">
                <SelectValue placeholder="All Stakes" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All Stakes</SelectItem>
                {filterOptions.stakes.map((s) => (
                  <SelectItem key={s} value={s}>{formatStakes(s)}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          {showGameMode && hasMultipleModes && (
            <Select
              value={gameModeValue}
              onValueChange={(v) => onGameModeChange?.(v === '__all__' ? '' : v)}
            >
              <SelectTrigger className="w-[130px] h-8 text-sm">
                <SelectValue placeholder="All Modes" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All Modes</SelectItem>
                {filterOptions!.game_modes.map((m) => (
                  <SelectItem key={m || '__reg__'} value={m || '__reg__'}>
                    {GAME_MODE_LABELS[m] || m}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          {showCheckpointSelect && (
            <Select
              value={checkpointSelectValue}
              onValueChange={handleCheckpointChange}
            >
              <SelectTrigger className="w-[180px] h-8 text-sm">
                <SelectValue>
                  {selectedCheckpoint
                    ? `Since: ${selectedCheckpoint.name}`
                    : 'All Time'}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all_time__">All Time</SelectItem>
                {sortedCheckpoints.length > 0 && <SelectSeparator />}
                {sortedCheckpoints.map((cp) => (
                  <SelectItem key={cp.id} value={String(cp.id)}>
                    {cp.name}
                    <span className="text-muted-foreground ml-1.5">
                      ({formatCheckpointDate(cp.checkpoint_at)})
                    </span>
                  </SelectItem>
                ))}
                {onCreateCheckpoint && (
                  <>
                    <SelectSeparator />
                    <SelectItem value="__new__">
                      <PlusIcon className="size-3.5 mr-1" />
                      New Checkpoint...
                    </SelectItem>
                  </>
                )}
              </SelectContent>
            </Select>
          )}

          {showDateRange && (
            <>
              <DatePicker
                value={dateFrom}
                onChange={(v) => onDateFromChange?.(v)}
                placeholder="From"
                className="h-8 text-sm"
              />
              <DatePicker
                value={dateTo}
                onChange={(v) => onDateToChange?.(v)}
                placeholder="To"
                className="h-8 text-sm"
              />
            </>
          )}

          {showDatePresets && (
            <div className="flex gap-1.5">
              {presetBtn('today', 'Today')}
              {presetBtn('week', 'Week')}
              {presetBtn('month', 'Month')}
              {presetBtn('all', 'All')}
            </div>
          )}

          {children && (
            <>
              <div className="flex-1" />
              {children}
            </>
          )}
        </CardContent>
      </Card>

      {/* New Checkpoint Dialog */}
      <Dialog open={newDialogOpen} onOpenChange={setNewDialogOpen}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle>New Checkpoint</DialogTitle>
            <DialogDescription>
              Mark a point in time to filter stats from.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-3 py-2">
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">Name</label>
              <Input
                ref={nameInputRef}
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="e.g., Strategy Change"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && newName.trim()) {
                    handleCreateCheckpoint();
                  }
                }}
              />
            </div>
            <div className="flex gap-3">
              <div className="flex flex-col gap-1.5 flex-1">
                <label className="text-sm font-medium">Date</label>
                <DatePicker
                  value={newDate}
                  onChange={(v) => setNewDate(v || new Date().toISOString().slice(0, 10))}
                  placeholder="Checkpoint date"
                  className="h-9 text-sm w-full"
                />
              </div>
              <div className="flex flex-col gap-1.5 w-24">
                <label className="text-sm font-medium">Time</label>
                <Input
                  type="time"
                  value={newTime}
                  onChange={(e) => setNewTime(e.target.value)}
                  className="h-9 text-sm"
                />
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">
                Note <span className="text-muted-foreground font-normal">(optional)</span>
              </label>
              <Input
                value={newNote}
                onChange={(e) => setNewNote(e.target.value)}
                placeholder="What changed?"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              onClick={handleCreateCheckpoint}
              disabled={!newName.trim() || creating}
            >
              {creating ? 'Creating...' : 'Create'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
