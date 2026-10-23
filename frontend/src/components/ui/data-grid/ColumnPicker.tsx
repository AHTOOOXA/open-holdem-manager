import { Settings2 } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

export interface ColumnPickerItem {
  id: string;
  label: string;
  visible: boolean;
  canHide: boolean;
}

/** Gear menu in the grid header's last cell: toggles stay open; the first column is locked. */
export function ColumnPicker({
  items,
  onToggle,
  onReset,
}: {
  items: ColumnPickerItem[];
  onToggle: (id: string, visible: boolean) => void;
  onReset: () => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        type="button"
        aria-label="Choose columns"
        title="Choose columns"
        className="inline-flex size-6 items-center justify-center rounded-control text-muted-foreground outline-none hover:bg-overlay-hover hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring data-[state=open]:bg-overlay-selected data-[state=open]:text-foreground"
      >
        <Settings2 className="size-3.5" aria-hidden />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="max-h-80 min-w-44 overflow-y-auto">
        <DropdownMenuLabel className="text-label text-muted-foreground">Columns</DropdownMenuLabel>
        {items.map((item) => (
          <DropdownMenuCheckboxItem
            key={item.id}
            checked={item.visible}
            disabled={!item.canHide}
            onCheckedChange={(v) => onToggle(item.id, v === true)}
            onSelect={(e) => e.preventDefault()}
          >
            {item.label}
          </DropdownMenuCheckboxItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={onReset}>Reset columns</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
