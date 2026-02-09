import { useState } from 'react';
import { Settings, RefreshCw, Trash2 } from 'lucide-react';
import { useImport } from '@/contexts/ImportContext';
import { SidebarFooter, SidebarMenu, SidebarMenuItem, SidebarMenuButton } from '@/components/ui/sidebar';
import { Input } from '@/components/ui/input';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';

export default function SidebarFooterSettings() {
  const { settings, handCount, phase, updateHeroName, startRebuild, clearDb } = useImport();
  const [editing, setEditing] = useState(false);
  const [nameInput, setNameInput] = useState('');

  const startEdit = () => {
    setNameInput(settings?.hero_username || '');
    setEditing(true);
  };

  const saveEdit = async () => {
    const trimmed = nameInput.trim();
    if (!trimmed) return;
    await updateHeroName(trimmed);
    setEditing(false);
  };

  return (
    <SidebarFooter>
      <SidebarMenu>
        <SidebarMenuItem>
          {editing ? (
            <div className="px-2 py-1">
              <Input
                className="h-7 text-xs"
                value={nameInput}
                onChange={(e) => setNameInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') saveEdit();
                  if (e.key === 'Escape') setEditing(false);
                }}
                autoFocus
                placeholder="Hero username"
              />
            </div>
          ) : (
            <div
              className="flex items-center justify-between px-2 py-1 group-data-[collapsible=icon]:hidden cursor-pointer hover:bg-sidebar-accent rounded-md"
              onClick={startEdit}
            >
              <div className="min-w-0">
                <div className="text-xs font-medium truncate">{settings?.hero_username || 'Set hero name'}</div>
                <div className="text-[10px] text-text-muted">{handCount.toLocaleString()} hands</div>
              </div>
            </div>
          )}
        </SidebarMenuItem>
        <SidebarMenuItem>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <SidebarMenuButton tooltip="Settings" className="group-data-[collapsible=icon]:justify-center">
                <Settings className="size-4" />
                <span className="group-data-[collapsible=icon]:hidden">Settings</span>
              </SidebarMenuButton>
            </DropdownMenuTrigger>
            <DropdownMenuContent side="right" align="end">
              <DropdownMenuItem
                disabled={handCount === 0 || phase !== 'idle'}
                onClick={() => {
                  if (!confirm('Rebuild all stats from stored hands? This re-parses everything with the latest parser.')) return;
                  startRebuild();
                }}
              >
                <RefreshCw className="size-4" />
                Rebuild Stats
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                variant="destructive"
                disabled={phase !== 'idle'}
                onClick={() => {
                  if (!confirm('Clear all hands from the database? This cannot be undone.')) return;
                  clearDb();
                }}
              >
                <Trash2 className="size-4" />
                Clear Database
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </SidebarMenuItem>
      </SidebarMenu>
    </SidebarFooter>
  );
}
