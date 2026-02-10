import type { DatePreset } from '@/lib/date-presets';
import type { FilterOptions } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { DatePicker } from '@/components/ui/date-picker';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

const GAME_MODE_LABELS: Record<string, string> = {
  '': 'Regular',
  'Fast Fold': 'Fast Fold',
};

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
}: FilterBarProps) {
  const presetBtn = (preset: DatePreset, label: string) => (
    <Button
      key={preset}
      variant={activePreset === preset ? 'default' : 'outline'}
      size="sm"
      className="h-7 text-xs"
      onClick={() => onPresetChange?.(preset)}
    >
      {label}
    </Button>
  );

  const hasMultipleModes = filterOptions?.game_modes && filterOptions.game_modes.length > 1;

  // "__all__" means no filter; gameMode prop is "" when not filtering,
  // but "" is also a valid game_mode value (Regular). We use "__all__" as the sentinel.
  const gameModeValue = gameMode === undefined || gameMode === '' ? '__all__' : gameMode;

  return (
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
                <SelectItem key={s} value={s}>{s}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        {showGameMode && hasMultipleModes && (
          <div className="flex gap-1">
            <Button
              variant={gameModeValue === '__all__' ? 'default' : 'outline'}
              size="sm"
              className="h-7 text-xs"
              onClick={() => onGameModeChange?.('')}
            >
              All
            </Button>
            {filterOptions!.game_modes.map((m) => (
              <Button
                key={m || '__reg__'}
                variant={gameModeValue === (m || '__reg__') ? 'default' : 'outline'}
                size="sm"
                className="h-7 text-xs"
                onClick={() => onGameModeChange?.(m || '__reg__')}
              >
                {GAME_MODE_LABELS[m] || m}
              </Button>
            ))}
          </div>
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
  );
}
