/**
 * Left panel of the Statistics screen: the dashboard tree (statistics-dashboards spec §2, own
 * implementation). Folders first then dashboards, ordinal names; inline rename (double-click, F2,
 * right after create / clone); context menu; keys F2, Delete, Ctrl/Cmd + X / V / Z / Y; search;
 * resizable 280-1000 px; collapsible. Structure edits go through `commit` (saved whole, undoable).
 *
 * Tree selection (the highlighted row) is separate from the shown dashboard: clicking a dashboard
 * shows it, clicking a folder only selects and opens / closes it, clicking empty space clears the
 * row selection. Folder expansion lives in memory per workspace.
 */
import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent, type MouseEvent, type PointerEvent } from 'react';
import { ChevronRight, ChevronsLeft, Folder, FolderOpen, FolderPlus, Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  ContextMenu, ContextMenuContent, ContextMenuItem, ContextMenuSeparator, ContextMenuShortcut, ContextMenuTrigger,
} from '@/components/ui/context-menu';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { expandedStore } from '@/lib/statistics/pages';
import type { DashboardsDoc } from '@/lib/statistics/types';
import {
  TREE_INDENT_PX, TREE_MAX_WIDTH, TREE_MIN_WIDTH, ancestorIds, canDelete, canMove, clampTreeWidth, cloneDashboard,
  createDashboard, createFolder, deleteNode, displayName, findNode, moveNode, renameNode, targetFolder, visibleRows,
} from '@/lib/statistics/tree';

const IS_MAC = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
const MOD = IS_MAC ? '⌘' : 'Ctrl+';
const RESIZE_STEP = 16;

export interface DashboardTreeProps {
  workspaceId: number;
  doc: DashboardsDoc;
  commit: (next: DashboardsDoc, opts?: { undoable?: boolean }) => void;
  /** Show a dashboard (saved as the selected one). */
  onShow: (id: number) => void;
  onCollapse: () => void;
  canUndo: boolean;
  canRedo: boolean;
  onUndo: () => void;
  onRedo: () => void;
  /** Start the inline rename of this node (e.g. after a clone from the dashboard's gear menu). */
  renameRequest?: { id: number; rev: number } | null;
}

export default function DashboardTree({
  workspaceId, doc, commit, onShow, onCollapse, canUndo, canRedo, onUndo, onRedo, renameRequest,
}: DashboardTreeProps) {
  const shownId = doc.config.selected_id;
  const [treeSel, setTreeSel] = useState<number | null>(shownId);
  const [expanded, setExpandedState] = useState<Set<number>>(() => {
    const stored = expandedStore.get(workspaceId);
    if (stored) return stored;
    // First visit: open the folders above the shown dashboard so its row is visible
    return new Set(shownId != null ? ancestorIds(doc.nodes, shownId) : []);
  });
  const [search, setSearch] = useState('');
  const [renaming, setRenamingState] = useState<number | null>(null);
  // Mirrors `renaming` for the context menu's focus restore (it must not steal the input's focus)
  const renamingRef = useRef<number | null>(null);
  const setRenaming = (id: number | null) => {
    renamingRef.current = id;
    setRenamingState(id);
  };
  const [cutId, setCutId] = useState<number | null>(null);
  const [menuTarget, setMenuTarget] = useState<number | null>(null);
  const [liveWidth, setLiveWidth] = useState<number | null>(null);
  const treeRef = useRef<HTMLDivElement>(null);
  const idBase = useId();
  const rowId = (id: number) => `${idBase}-row-${id}`;
  const drag = useRef<{ startX: number; startW: number; w: number } | null>(null);

  const setExpanded = (fn: (s: Set<number>) => Set<number>) => {
    setExpandedState((prev) => {
      const next = fn(prev);
      expandedStore.set(workspaceId, next);
      return next;
    });
  };
  const expand = (ids: number[]) => setExpanded((s) => {
    if (ids.every((i) => s.has(i))) return s;
    const n = new Set(s);
    for (const i of ids) n.add(i);
    return n;
  });
  const toggle = (id: number) => setExpanded((s) => {
    const n = new Set(s);
    if (n.has(id)) n.delete(id); else n.add(id);
    return n;
  });

  // A rename asked for from outside: applied once per request (render-time state update)
  const [seenRename, setSeenRename] = useState(() => renameRequest?.rev ?? 0);
  if (renameRequest && renameRequest.rev !== seenRename) {
    setSeenRename(renameRequest.rev);
    setTreeSel(renameRequest.id);
    setRenamingState(renameRequest.id);
    const up = ancestorIds(doc.nodes, renameRequest.id);
    if (up.some((i) => !expanded.has(i))) {
      const next = new Set([...expanded, ...up]);
      expandedStore.set(workspaceId, next);
      setExpandedState(next);
    }
  }

  const rows = useMemo(() => visibleRows(doc.nodes, expanded, search), [doc.nodes, expanded, search]);
  const selNode = findNode(doc, treeSel);
  const width = liveWidth ?? doc.config.tree_width;

  const focusTree = () => requestAnimationFrame(() => treeRef.current?.focus());

  // ── Actions (target = a right-clicked row, else the tree selection)
  const reveal = (id: number, nodes = doc.nodes) => expand(ancestorIds(nodes, id));

  const createDash = (anchor: number | null) => {
    const r = createDashboard(doc, targetFolder(doc, anchor));
    setSearch('');
    commit(r.doc, { undoable: true });
    reveal(r.id, r.doc.nodes);
    setTreeSel(r.id);
    setRenaming(r.id);
  };
  const createFold = (anchor: number | null) => {
    const r = createFolder(doc, targetFolder(doc, anchor));
    setSearch('');
    commit(r.doc, { undoable: true });
    reveal(r.id, r.doc.nodes);
    setTreeSel(r.id);
    setRenaming(r.id);
  };
  const clone = (id: number) => {
    const r = cloneDashboard(doc, id);
    if (!r) return;
    commit(r.doc, { undoable: true });
    reveal(r.id, r.doc.nodes);
    setTreeSel(r.id);
    setRenaming(r.id);
  };
  const remove = (id: number) => {
    if (!canDelete(doc, id)) return;
    commit(deleteNode(doc, id), { undoable: true });
    if (treeSel === id) setTreeSel(null);
    if (cutId === id) setCutId(null);
  };
  const paste = (anchor: number | null) => {
    if (cutId == null) return;
    const parent = targetFolder(doc, anchor);
    if (!canMove(doc, cutId, parent)) return;
    const next = moveNode(doc, cutId, parent);
    commit(next, { undoable: true });
    if (parent != null) expand([parent, ...ancestorIds(next.nodes, parent)]);
    setTreeSel(cutId);
    setCutId(null);
  };
  const finishRename = (id: number, name: string | null) => {
    setRenaming(null);
    if (name != null) commit(renameNode(doc, id, name), { undoable: true });
    focusTree();
  };

  const clickRow = (id: number) => {
    const n = findNode(doc, id);
    if (!n) return;
    setTreeSel(id);
    if (n.kind === 'folder') toggle(id);
    else onShow(id);
  };

  // ── Keyboard (tree focused; the rename input stops its own keys)
  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const mod = e.metaKey || e.ctrlKey;
    const key = e.key.toLowerCase();
    const idx = rows.findIndex((r) => r.node.id === treeSel);
    const move = (to: number) => {
      const r = rows[Math.max(0, Math.min(rows.length - 1, to))];
      if (!r) return;
      setTreeSel(r.node.id);
      if (r.node.kind === 'dashboard') onShow(r.node.id);
    };
    let handled = true;
    if (e.key === 'F2' && treeSel != null) setRenaming(treeSel);
    else if ((e.key === 'Delete' || (IS_MAC && e.key === 'Backspace' && mod)) && treeSel != null) remove(treeSel);
    else if (mod && key === 'x' && treeSel != null) setCutId(treeSel);
    else if (mod && key === 'v') paste(treeSel);
    else if (mod && ((key === 'z' && e.shiftKey) || key === 'y')) onRedo();
    else if (mod && key === 'z') onUndo();
    else if (e.key === 'ArrowDown') move(idx < 0 ? 0 : idx + 1);
    else if (e.key === 'ArrowUp') move(idx < 0 ? 0 : idx - 1);
    else if (e.key === 'ArrowRight' && selNode?.kind === 'folder') expand([selNode.id]);
    else if (e.key === 'ArrowLeft' && selNode) {
      if (selNode.kind === 'folder' && expanded.has(selNode.id) && !search) toggle(selNode.id);
      else if (selNode.parent_id != null) setTreeSel(selNode.parent_id);
    } else if (e.key === 'Enter' && selNode) clickRow(selNode.id);
    else if (e.key === 'Escape' && cutId != null) setCutId(null);
    else handled = false;
    if (handled) e.preventDefault();
  };

  // ── Resize thumb
  const onPointerDown = (e: PointerEvent<HTMLDivElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = { startX: e.clientX, startW: width, w: width };
  };
  const onPointerMove = (e: PointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    if (!d) return;
    d.w = clampTreeWidth(d.startW + e.clientX - d.startX);
    setLiveWidth(d.w);
  };
  const endDrag = () => {
    const d = drag.current;
    drag.current = null;
    if (!d) return;
    setLiveWidth(null);
    commit({ ...doc, config: { ...doc.config, tree_width: d.w } });
  };
  const onResizeKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const step = e.shiftKey ? RESIZE_STEP * 4 : RESIZE_STEP;
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
    e.preventDefault();
    const w = clampTreeWidth(width + (e.key === 'ArrowRight' ? step : -step));
    commit({ ...doc, config: { ...doc.config, tree_width: w } });
  };

  // ── Context menu
  const target = findNode(doc, menuTarget);
  const pasteOk = cutId != null && canMove(doc, cutId, targetFolder(doc, menuTarget));

  return (
    <aside
      aria-label="Dashboards"
      className="relative flex shrink-0 flex-col border-r border-border bg-card"
      style={{ width }}
    >
      <div className="flex items-center justify-between gap-2 py-2 pr-1 pl-2">
        <Button size="sm" onClick={() => createDash(treeSel)}>
          <Plus /> Create Dashboard
        </Button>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon-sm" className="text-muted-foreground hover:text-foreground" aria-label="Collapse dashboards" onClick={onCollapse}>
              <ChevronsLeft />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Collapse</TooltipContent>
        </Tooltip>
      </div>

      <div className="flex items-center gap-1 pr-1 pb-2 pl-2">
        <Input
          type="search"
          aria-label="Search dashboards"
          placeholder="Type here to search..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="h-control rounded-pill px-3"
        />
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon-sm" className="text-muted-foreground hover:text-foreground" aria-label="Create Folder" onClick={() => createFold(treeSel)}>
              <FolderPlus />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Create Folder</TooltipContent>
        </Tooltip>
      </div>

      <ContextMenu>
        <ContextMenuTrigger asChild>
          <div
            className="min-h-0 flex-1"
            onContextMenuCapture={(e) => {
              // Shift+F10 / Menu key on the focused tree (not on a row): act on the selected node
              const keyboard = e.target === treeRef.current && e.button === 0 && document.activeElement === treeRef.current;
              setMenuTarget(keyboard ? treeSel : null);
            }}
          >
            <ScrollArea className="h-full">
              <div
                ref={treeRef}
                role="tree"
                aria-label="Dashboard tree"
                tabIndex={0}
                aria-activedescendant={treeSel != null && rows.some((r) => r.node.id === treeSel) ? rowId(treeSel) : undefined}
                onKeyDown={onKeyDown}
                onClick={(e: MouseEvent) => { if (e.target === e.currentTarget) setTreeSel(null); }}
                className="group/tree flex min-h-40 flex-col px-1 pb-4 outline-none"
              >
                {rows.length === 0 && (
                  <p className="px-3 py-2 text-sm text-subtle-foreground">{search ? 'Nothing matches' : 'No dashboards'}</p>
                )}
                {rows.map(({ node, level, expanded: open }) => {
                  const isFolder = node.kind === 'folder';
                  const selected = node.id === treeSel;
                  const shown = !isFolder && node.id === shownId;
                  return (
                    <div
                      key={node.id}
                      id={rowId(node.id)}
                      role="treeitem"
                      aria-level={level + 1}
                      aria-selected={selected}
                      aria-expanded={isFolder ? open : undefined}
                      aria-current={shown ? 'page' : undefined}
                      onClick={() => clickRow(node.id)}
                      onDoubleClick={() => setRenaming(node.id)}
                      onContextMenu={() => { setMenuTarget(node.id); setTreeSel(node.id); }}
                      className={cn(
                        'flex h-row-tree shrink-0 cursor-pointer items-center gap-1.5 rounded-control pr-2 text-sm select-none',
                        selected
                          ? 'bg-overlay-selected group-focus-visible/tree:ring-1 group-focus-visible/tree:ring-ring group-focus-visible/tree:ring-inset'
                          : 'hover:bg-overlay-hover',
                        shown && 'text-primary',
                        node.id === cutId && 'opacity-50',
                      )}
                      style={{ paddingLeft: 8 + level * TREE_INDENT_PX }}
                    >
                      {isFolder ? (
                        <>
                          <ChevronRight
                            aria-hidden
                            className={cn('size-3 shrink-0 text-muted-foreground transition-transform', open && 'rotate-90')}
                          />
                          {open
                            ? <FolderOpen aria-hidden className="size-4 shrink-0 text-muted-foreground" />
                            : <Folder aria-hidden className="size-4 shrink-0 text-muted-foreground" />}
                        </>
                      ) : (
                        <span aria-hidden className="w-3 shrink-0" />
                      )}
                      {renaming === node.id ? (
                        <RenameInput name={node.name} onDone={(name) => finishRename(node.id, name)} />
                      ) : (
                        <span className={cn('min-w-0 truncate', isFolder && 'font-semibold')}>{displayName(node.name)}</span>
                      )}
                    </div>
                  );
                })}
              </div>
            </ScrollArea>
          </div>
        </ContextMenuTrigger>
        <ContextMenuContent
          className="min-w-52"
          onCloseAutoFocus={(e) => {
            e.preventDefault();
            // A rename started from the menu: its input mounted while the menu held focus
            if (renamingRef.current == null) treeRef.current?.focus();
            else treeRef.current?.querySelector<HTMLInputElement>('input')?.focus();
          }}
        >
          <ContextMenuItem onSelect={() => createFold(menuTarget)}>Create Folder</ContextMenuItem>
          <ContextMenuSeparator />
          {cutId != null && (
            <ContextMenuItem disabled={!pasteOk} onSelect={() => paste(menuTarget)}>
              Paste <ContextMenuShortcut>{MOD}V</ContextMenuShortcut>
            </ContextMenuItem>
          )}
          <ContextMenuItem disabled={!target} onSelect={() => target && setRenaming(target.id)}>
            Rename <ContextMenuShortcut>F2</ContextMenuShortcut>
          </ContextMenuItem>
          <ContextMenuItem disabled={!target} onSelect={() => target && setCutId(target.id)}>
            Cut <ContextMenuShortcut>{MOD}X</ContextMenuShortcut>
          </ContextMenuItem>
          {(canUndo || canRedo) && (
            <>
              <ContextMenuSeparator />
              {canUndo && (
                <ContextMenuItem onSelect={onUndo}>
                  Undo <ContextMenuShortcut>{MOD}Z</ContextMenuShortcut>
                </ContextMenuItem>
              )}
              {canRedo && (
                <ContextMenuItem onSelect={onRedo}>
                  Redo <ContextMenuShortcut>{MOD}Y</ContextMenuShortcut>
                </ContextMenuItem>
              )}
            </>
          )}
          <ContextMenuSeparator />
          <ContextMenuItem onSelect={() => createDash(menuTarget)}>Create Dashboard</ContextMenuItem>
          {target?.kind === 'dashboard' && (
            <>
              <ContextMenuItem onSelect={() => clone(target.id)}>Clone Dashboard</ContextMenuItem>
              <ContextMenuItem disabled={!canDelete(doc, target.id)} onSelect={() => remove(target.id)}>
                Delete Dashboard <ContextMenuShortcut>Del</ContextMenuShortcut>
              </ContextMenuItem>
            </>
          )}
          {target?.kind === 'folder' && (
            <>
              <ContextMenuSeparator />
              <ContextMenuItem disabled={!canDelete(doc, target.id)} onSelect={() => remove(target.id)}>
                Delete Folder <ContextMenuShortcut>Del</ContextMenuShortcut>
              </ContextMenuItem>
            </>
          )}
        </ContextMenuContent>
      </ContextMenu>

      <div
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize dashboards panel"
        aria-valuenow={width}
        aria-valuemin={TREE_MIN_WIDTH}
        aria-valuemax={TREE_MAX_WIDTH}
        tabIndex={0}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onKeyDown={onResizeKey}
        className="absolute inset-y-0 -right-0.5 z-(--z-sticky) w-1 cursor-ew-resize touch-none outline-none hover:bg-primary/40 focus-visible:bg-primary/60"
      />
    </aside>
  );
}

function RenameInput({ name, onDone }: { name: string; onDone: (name: string | null) => void }) {
  const done = useRef(false);
  const ref = useRef<HTMLInputElement>(null);
  // Started from a menu: take the focus once the menu has let it go
  useEffect(() => {
    const t = setTimeout(() => {
      if (!done.current && document.activeElement !== ref.current) ref.current?.focus();
    }, 200);
    return () => clearTimeout(t);
  }, []);
  const finish = (v: string | null) => {
    if (done.current) return;
    done.current = true;
    onDone(v);
  };
  return (
    <Input
      ref={ref}
      autoFocus
      aria-label="Name"
      defaultValue={name}
      maxLength={200}
      onFocus={(e) => e.currentTarget.select()}
      onClick={(e) => e.stopPropagation()}
      onDoubleClick={(e) => e.stopPropagation()}
      onKeyDown={(e) => {
        e.stopPropagation();
        if (e.key === 'Enter') { e.preventDefault(); finish(e.currentTarget.value); }
        else if (e.key === 'Escape') { e.preventDefault(); finish(null); }
      }}
      onBlur={(e) => finish(e.currentTarget.value)}
      className="h-6 min-w-0 flex-1 border-primary px-1.5 text-sm"
    />
  );
}
