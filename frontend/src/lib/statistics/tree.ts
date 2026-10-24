/**
 * Pure helpers for the Statistics dashboard tree (folders + dashboards, one document per
 * workspace; contract in ./types.ts). Every edit returns a new document, or the same object when
 * the edit is refused, so callers can skip the save with `next === doc`.
 *
 * Rules: folders first, then dashboards, each by ordinal (case-sensitive) name; new names are
 * made unique among their siblings with " (1)", " (2)"...; a folder can only be deleted when
 * empty; the last dashboard can never be deleted; a node can't be moved into itself or below.
 */
import type { DashboardDefinition, DashboardNode, DashboardsConfig, DashboardsDoc } from './types';

export const TREE_MIN_WIDTH = 280;
export const TREE_MAX_WIDTH = 1000;
export const TREE_DEFAULT_WIDTH = 300;
export const TREE_INDENT_PX = 14;
export const NAME_MAX = 200;

export const NEW_DASHBOARD_NAME = 'new dashboard';
export const NEW_FOLDER_NAME = 'New Folder';

export const DEFAULT_DEFINITION: DashboardDefinition = { player_id: null, filters: [], profile_id: 'default' };

export type FolderNode = Extract<DashboardNode, { kind: 'folder' }>;
export type DashboardLeaf = Extract<DashboardNode, { kind: 'dashboard' }>;

export function clampTreeWidth(px: number): number {
  if (!Number.isFinite(px)) return TREE_DEFAULT_WIDTH;
  return Math.min(TREE_MAX_WIDTH, Math.max(TREE_MIN_WIDTH, Math.round(px)));
}

/** "a->b" is shown as "a→b" (names are stored as typed). */
export function displayName(name: string): string {
  return name.replace(/->/g, '→');
}

/** Ordinal string order (code units), like the reference: "B" < "a". */
function ordinal(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

export function compareNodes(a: DashboardNode, b: DashboardNode): number {
  if (a.kind !== b.kind) return a.kind === 'folder' ? -1 : 1;
  return ordinal(a.name, b.name) || a.id - b.id;
}

export function findNode(doc: DashboardsDoc, id: number | null | undefined): DashboardNode | undefined {
  if (id == null) return undefined;
  return doc.nodes.find((n) => n.id === id);
}

export function findDashboard(doc: DashboardsDoc, id: number | null | undefined): DashboardLeaf | undefined {
  const n = findNode(doc, id);
  return n?.kind === 'dashboard' ? n : undefined;
}

export function childrenOf(nodes: readonly DashboardNode[], parentId: number | null): DashboardNode[] {
  return nodes.filter((n) => n.parent_id === parentId).sort(compareNodes);
}

export function hasChildren(nodes: readonly DashboardNode[], id: number): boolean {
  return nodes.some((n) => n.parent_id === id);
}

export function dashboardCount(doc: DashboardsDoc): number {
  return doc.nodes.reduce((n, x) => n + (x.kind === 'dashboard' ? 1 : 0), 0);
}

/** Every node in display order (depth first, folders first), regardless of expansion. */
export function treeOrder(nodes: readonly DashboardNode[]): DashboardNode[] {
  const out: DashboardNode[] = [];
  const walk = (parent: number | null) => {
    for (const n of childrenOf(nodes, parent)) {
      out.push(n);
      if (n.kind === 'folder') walk(n.id);
    }
  };
  walk(null);
  return out;
}

export function firstDashboardId(doc: DashboardsDoc): number | null {
  return treeOrder(doc.nodes).find((n) => n.kind === 'dashboard')?.id ?? null;
}

/** Ids of the folders above `id`, nearest first. */
export function ancestorIds(nodes: readonly DashboardNode[], id: number): number[] {
  const out: number[] = [];
  const seen = new Set<number>();
  let cur = nodes.find((n) => n.id === id)?.parent_id ?? null;
  while (cur != null && !seen.has(cur)) {
    seen.add(cur);
    out.push(cur);
    cur = nodes.find((n) => n.id === cur)?.parent_id ?? null;
  }
  return out;
}

/** True when `id` is `ancestor` or lies anywhere below it. */
export function isWithin(nodes: readonly DashboardNode[], id: number, ancestor: number): boolean {
  return id === ancestor || ancestorIds(nodes, id).includes(ancestor);
}

export function nextNodeId(nodes: readonly DashboardNode[]): number {
  return nodes.reduce((m, n) => Math.max(m, n.id), 0) + 1;
}

/** `base`, else "base (1)", "base (2)"... — first one not in `taken`. */
export function uniqueName(base: string, taken: Iterable<string>): string {
  const set = new Set(taken);
  if (!set.has(base)) return base;
  for (let i = 1; ; i++) {
    const name = `${base} (${i})`;
    if (!set.has(name)) return name;
  }
}

/** "Me (3)" -> "Me"; names without a trailing " (n)" are returned trimmed. */
export function stripCopySuffix(name: string): string {
  return name.replace(/\s*\(\d+\)\s*$/, '').trim() || name.trim();
}

function siblingNames(nodes: readonly DashboardNode[], parentId: number | null, exceptId?: number): string[] {
  return nodes.filter((n) => n.parent_id === parentId && n.id !== exceptId).map((n) => n.name);
}

/** The folder new items go into: a selected folder itself, a selected dashboard's folder, else the root. */
export function targetFolder(doc: DashboardsDoc, selectedId: number | null): number | null {
  const n = findNode(doc, selectedId);
  if (!n) return null;
  return n.kind === 'folder' ? n.id : n.parent_id;
}

function withConfig(doc: DashboardsDoc, patch: Partial<DashboardsConfig>): DashboardsDoc {
  return { ...doc, config: { ...doc.config, ...patch } };
}

/** selected_id must name a dashboard; fall back to the first one in tree order. */
export function withValidSelection(doc: DashboardsDoc): DashboardsDoc {
  if (findDashboard(doc, doc.config.selected_id)) return doc;
  return withConfig(doc, { selected_id: firstDashboardId(doc) });
}

export interface Created {
  doc: DashboardsDoc;
  id: number;
}

/** New dashboard "new dashboard" (made unique) in `parentId`, selected. */
export function createDashboard(
  doc: DashboardsDoc,
  parentId: number | null,
  definition: DashboardDefinition = DEFAULT_DEFINITION,
): Created {
  const id = nextNodeId(doc.nodes);
  const node: DashboardLeaf = {
    id,
    kind: 'dashboard',
    name: uniqueName(NEW_DASHBOARD_NAME, siblingNames(doc.nodes, parentId)),
    parent_id: parentId,
    definition: structuredClone(definition),
  };
  return { doc: withConfig({ ...doc, nodes: [...doc.nodes, node] }, { selected_id: id }), id };
}

/** New folder "New Folder" (made unique) in `parentId`. The shown dashboard does not change. */
export function createFolder(doc: DashboardsDoc, parentId: number | null): Created {
  const id = nextNodeId(doc.nodes);
  const node: FolderNode = {
    id,
    kind: 'folder',
    name: uniqueName(NEW_FOLDER_NAME, siblingNames(doc.nodes, parentId)),
    parent_id: parentId,
  };
  return { doc: { ...doc, nodes: [...doc.nodes, node] }, id };
}

/** Copy of a dashboard's definition next to it, named after it ("Me" -> "Me (1)"), selected. */
export function cloneDashboard(doc: DashboardsDoc, id: number): Created | null {
  const src = findDashboard(doc, id);
  if (!src) return null;
  const newId = nextNodeId(doc.nodes);
  const node: DashboardLeaf = {
    id: newId,
    kind: 'dashboard',
    name: uniqueName(stripCopySuffix(src.name), siblingNames(doc.nodes, src.parent_id)),
    parent_id: src.parent_id,
    definition: structuredClone(src.definition),
  };
  return { doc: withConfig({ ...doc, nodes: [...doc.nodes, node] }, { selected_id: newId }), id: newId };
}

/** Rename (trimmed, at most 200 chars). Empty or unchanged names leave the doc as is. */
export function renameNode(doc: DashboardsDoc, id: number, name: string): DashboardsDoc {
  const clean = name.trim().slice(0, NAME_MAX);
  const n = findNode(doc, id);
  if (!n || !clean || clean === n.name) return doc;
  return { ...doc, nodes: doc.nodes.map((x) => (x.id === id ? { ...x, name: clean } : x)) };
}

export function canDelete(doc: DashboardsDoc, id: number | null): boolean {
  const n = findNode(doc, id);
  if (!n) return false;
  if (n.kind === 'folder') return !hasChildren(doc.nodes, n.id);
  return dashboardCount(doc) > 1;
}

/** Delete an empty folder or a dashboard (never the last one). A deleted shown dashboard hands over to the first one. */
export function deleteNode(doc: DashboardsDoc, id: number): DashboardsDoc {
  if (!canDelete(doc, id)) return doc;
  return withValidSelection({ ...doc, nodes: doc.nodes.filter((n) => n.id !== id) });
}

export function canMove(doc: DashboardsDoc, id: number, parentId: number | null): boolean {
  const n = findNode(doc, id);
  if (!n) return false;
  if (parentId !== null) {
    const p = findNode(doc, parentId);
    if (!p || p.kind !== 'folder') return false;
    if (isWithin(doc.nodes, parentId, id)) return false;
  }
  return n.parent_id !== parentId;
}

/** Move a node into another folder (Cut + Paste); its name is made unique there. */
export function moveNode(doc: DashboardsDoc, id: number, parentId: number | null): DashboardsDoc {
  if (!canMove(doc, id, parentId)) return doc;
  const n = findNode(doc, id)!;
  const name = uniqueName(n.name, siblingNames(doc.nodes, parentId, id));
  return { ...doc, nodes: doc.nodes.map((x) => (x.id === id ? { ...x, parent_id: parentId, name } : x)) };
}

export function setDefinition(doc: DashboardsDoc, id: number, definition: DashboardDefinition): DashboardsDoc {
  if (!findDashboard(doc, id)) return doc;
  return {
    ...doc,
    nodes: doc.nodes.map((x) => (x.id === id && x.kind === 'dashboard' ? { ...x, definition } : x)),
  };
}

export function selectDashboard(doc: DashboardsDoc, id: number): DashboardsDoc {
  if (!findDashboard(doc, id) || doc.config.selected_id === id) return doc;
  return withConfig(doc, { selected_id: id });
}

export function setTreeWidth(doc: DashboardsDoc, px: number): DashboardsDoc {
  const w = clampTreeWidth(px);
  return w === doc.config.tree_width ? doc : withConfig(doc, { tree_width: w });
}

export function setCollapsed(doc: DashboardsDoc, collapsed: boolean): DashboardsDoc {
  return collapsed === doc.config.collapsed ? doc : withConfig(doc, { collapsed });
}

// ── Search and visible rows ─────────────────────────────────────────────────────────────────

/**
 * Case-insensitive substring match; with 2+ words (each longer than one character) a name also
 * matches when it contains every word, in any order.
 */
export function matchesSearch(name: string, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const n = name.toLowerCase();
  if (n.includes(q)) return true;
  const words = q.split(/\s+/).filter((w) => w.length > 1);
  return words.length >= 2 && words.every((w) => n.includes(w));
}

export interface TreeRow {
  node: DashboardNode;
  level: number;
  /** Folders only: shown open (always true while searching). */
  expanded: boolean;
  hasChildren: boolean;
}

/**
 * The rows to draw. Without a search: folders open per `expanded`. With a search: the matching
 * items plus their parent folders (all open), in normal order.
 */
export function visibleRows(nodes: readonly DashboardNode[], expanded: ReadonlySet<number>, search = ''): TreeRow[] {
  const q = search.trim();
  let keep: Set<number> | null = null;
  if (q) {
    keep = new Set<number>();
    for (const n of nodes) {
      if (!matchesSearch(n.name, q)) continue;
      keep.add(n.id);
      for (const a of ancestorIds(nodes, n.id)) keep.add(a);
    }
  }
  const out: TreeRow[] = [];
  const walk = (parent: number | null, level: number) => {
    for (const n of childrenOf(nodes, parent)) {
      if (keep && !keep.has(n.id)) continue;
      const isOpen = n.kind === 'folder' && (keep ? true : expanded.has(n.id));
      out.push({ node: n, level, expanded: isOpen, hasChildren: n.kind === 'folder' && hasChildren(nodes, n.id) });
      if (n.kind === 'folder' && isOpen) walk(n.id, level + 1);
    }
  };
  walk(null, 0);
  return out;
}

// ── Undo / redo (session only) ──────────────────────────────────────────────────────────────

export interface History {
  past: DashboardNode[][];
  future: DashboardNode[][];
}

export const EMPTY_HISTORY: History = { past: [], future: [] };
const HISTORY_LIMIT = 100;

/** Record `before` (the nodes prior to an undoable edit); clears the redo side. */
export function pushHistory(h: History, before: DashboardNode[]): History {
  return { past: [...h.past, before].slice(-HISTORY_LIMIT), future: [] };
}

/**
 * Structure only: restored dashboards keep their current definition (definition changes are not
 * undoable), config is kept and the selection repaired.
 */
function restore(doc: DashboardsDoc, nodes: DashboardNode[]): DashboardsDoc {
  const current = new Map(doc.nodes.map((n) => [n.id, n]));
  const merged = nodes.map((n) => {
    const cur = current.get(n.id);
    return n.kind === 'dashboard' && cur?.kind === 'dashboard' ? { ...n, definition: cur.definition } : n;
  });
  return withValidSelection({ ...doc, nodes: merged });
}

/** Undo: restore the last recorded tree structure. */
export function undo(h: History, doc: DashboardsDoc): { doc: DashboardsDoc; history: History } | null {
  const prev = h.past[h.past.length - 1];
  if (!prev) return null;
  return {
    doc: restore(doc, prev),
    history: { past: h.past.slice(0, -1), future: [doc.nodes, ...h.future] },
  };
}

export function redo(h: History, doc: DashboardsDoc): { doc: DashboardsDoc; history: History } | null {
  const next = h.future[0];
  if (!next) return null;
  return {
    doc: restore(doc, next),
    history: { past: [...h.past, doc.nodes], future: h.future.slice(1) },
  };
}
