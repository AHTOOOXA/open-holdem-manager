import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Settings, RefreshCw, Trash2, Download, Upload, RotateCw, ExternalLink, ArrowDownToLine } from 'lucide-react';
import { useImport } from '@/contexts/ImportContext';
import { useWorkspace } from '@/contexts/WorkspaceContext';
import { SidebarFooter, SidebarMenu, SidebarMenuItem, SidebarMenuButton } from '@/components/ui/sidebar';
import { Button } from '@/components/ui/button';
import { getHeroes } from '@/lib/api';
import { heroLabel } from '@/lib/hero-accounts';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuLabel,
} from '@/components/ui/dropdown-menu';

export default function SidebarFooterSettings() {
  const { phase, startRebuild, clearDb, exportDatabase, importDatabase } = useImport();
  const { activeWorkspace } = useWorkspace();
  const navigate = useNavigate();
  const { data: heroes } = useQuery({
    queryKey: ['heroes', activeWorkspace?.id],
    queryFn: () => getHeroes(activeWorkspace!.id),
    enabled: !!activeWorkspace,
  });
  const handCount = activeWorkspace?.hand_count ?? 0;
  const dbFileRef = useRef<HTMLInputElement>(null);
  const [updateVersion, setUpdateVersion] = useState<string | null>(null);
  const [updateReady, setUpdateReady] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const canAutoUpdate = (window as any).electronAPI?.platform === 'win32';

  useEffect(() => {
    const handler = (e: Event) => {
      const { version, ready } = (e as CustomEvent).detail;
      setUpdateVersion(version);
      setUpdateReady(ready);
    };
    window.addEventListener('ohm-update-state', handler);
    return () => window.removeEventListener('ohm-update-state', handler);
  }, []);

  return (
    <SidebarFooter>
      <SidebarMenu>
        <SidebarMenuItem>
          <Button
            type="button"
            variant="ghost"
            className="h-auto w-full justify-start px-2 py-1 text-left group-data-[collapsible=icon]:hidden hover:bg-sidebar-accent dark:hover:bg-sidebar-accent"
            title="Hero accounts"
            onClick={() => navigate('/settings/workspaces')}
          >
              <div className="min-w-0">
                <div className="text-xs font-medium truncate">{heroLabel(heroes?.active)}</div>
                <div className="text-[10px] text-text-muted">{handCount.toLocaleString()} hands</div>
              </div>
          </Button>
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
                disabled={handCount === 0 || phase !== 'idle'}
                onClick={() => exportDatabase()}
              >
                <Download className="size-4" />
                Export Database
              </DropdownMenuItem>
              <DropdownMenuItem
                disabled={phase !== 'idle'}
                onClick={() => dbFileRef.current?.click()}
              >
                <Upload className="size-4" />
                Import Database
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
              <DropdownMenuSeparator />
              {updateReady && canAutoUpdate ? (
                <DropdownMenuItem
                  onClick={() => {
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    (window as any).electronAPI?.installUpdate?.();
                  }}
                >
                  <ArrowDownToLine className="size-4" />
                  Restart to Update (v{updateVersion})
                </DropdownMenuItem>
              ) : updateVersion ? (
                canAutoUpdate ? (
                  <DropdownMenuItem
                    onClick={() => {
                      // eslint-disable-next-line @typescript-eslint/no-explicit-any
                      (window as any).electronAPI?.downloadUpdate?.();
                    }}
                  >
                    <ArrowDownToLine className="size-4" />
                    Download v{updateVersion}
                  </DropdownMenuItem>
                ) : (
                  <DropdownMenuItem
                    onClick={() => {
                      // eslint-disable-next-line @typescript-eslint/no-explicit-any
                      (window as any).electronAPI?.openExternal?.(
                        `https://github.com/AHTOOOXA/open-holdem-manager/releases/tag/v${updateVersion}`
                      );
                    }}
                  >
                    <ExternalLink className="size-4" />
                    Download v{updateVersion}
                  </DropdownMenuItem>
                )
              ) : (
                <DropdownMenuItem
                  onClick={() => {
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    (window as any).electronAPI?.checkForUpdates?.();
                  }}
                >
                  <RotateCw className="size-4" />
                  Check for Updates
                </DropdownMenuItem>
              )}
              <DropdownMenuLabel className="text-[10px] font-normal text-muted-foreground/50">
                v{__APP_VERSION__}
              </DropdownMenuLabel>
            </DropdownMenuContent>
          </DropdownMenu>
        </SidebarMenuItem>
      </SidebarMenu>
      <input
        ref={dbFileRef}
        type="file"
        accept=".duckdb"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (!file) return;
          if (!confirm(`Replace current database with "${file.name}"? A backup will be saved as poker.duckdb.bak.`)) {
            e.target.value = '';
            return;
          }
          importDatabase(file);
          e.target.value = '';
        }}
      />
    </SidebarFooter>
  );
}
