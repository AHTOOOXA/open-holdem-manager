/**
 * Pure helpers for the hand-list gestures (M8): when the docked hand panel fits, which row an arrow key
 * selects, and the hover-intent timing behind the quick-replay popover. Spec: replayer §1 and §7 (own words).
 */

/** Below this container width the hand panel does not dock next to the list; the drawer opens instead. */
export const HAND_PANEL_MIN_CONTAINER_WIDTH = 1100;
/** Hover the round replay button this long to open the quick replay. */
export const QUICK_REPLAY_OPEN_MS = 300;
/** The quick replay advances one step this often. */
export const QUICK_REPLAY_STEP_MS = 300;
/** Grace between leaving the button/popover and closing, so the pointer can cross the gap between them. */
export const QUICK_REPLAY_CLOSE_GRACE_MS = 120;

/** The panel docks only once the container has been measured and is wide enough. */
export function canDockPanel(containerWidth: number | null): boolean {
  return containerWidth !== null && containerWidth >= HAND_PANEL_MIN_CONTAINER_WIDTH;
}

/** The id `delta` rows away from `current` (clamped to the list); null for an empty list. */
export function neighbourId(ids: readonly string[], current: string | null, delta: number): string | null {
  if (ids.length === 0) return null;
  const at = current === null ? -1 : ids.indexOf(current);
  if (at < 0) return delta >= 0 ? ids[0] : ids[ids.length - 1];
  return ids[Math.max(0, Math.min(ids.length - 1, at + delta))];
}

export interface HoverIntentOptions {
  openDelay: number;
  closeDelay: number;
  onOpen: () => void;
  onClose: () => void;
}

export interface HoverIntent {
  /** Pointer entered the trigger or the popover. */
  enter: () => void;
  /** Pointer left the trigger or the popover. */
  leave: () => void;
  /** Open immediately (keyboard / click). */
  openNow: () => void;
  /** A pinned popover ignores pointer leave (checked when the close timer fires). */
  setPinned: (pinned: boolean) => void;
  /** The popover closed by itself (Esc, outside click): forget the open state. */
  notifyClosed: () => void;
  dispose: () => void;
}

/** Open after `openDelay` of hovering; close `closeDelay` after the pointer left both trigger and popover. */
export function createHoverIntent(o: HoverIntentOptions): HoverIntent {
  let open = false;
  let pinned = false;
  let openTimer: ReturnType<typeof setTimeout> | undefined;
  let closeTimer: ReturnType<typeof setTimeout> | undefined;
  const clearOpen = () => {
    if (openTimer !== undefined) clearTimeout(openTimer);
    openTimer = undefined;
  };
  const clearClose = () => {
    if (closeTimer !== undefined) clearTimeout(closeTimer);
    closeTimer = undefined;
  };
  return {
    enter() {
      clearClose();
      if (!open && openTimer === undefined) {
        openTimer = setTimeout(() => {
          openTimer = undefined;
          open = true;
          o.onOpen();
        }, o.openDelay);
      }
    },
    leave() {
      clearOpen();
      if (open && closeTimer === undefined) {
        closeTimer = setTimeout(() => {
          closeTimer = undefined;
          if (pinned) return;
          open = false;
          o.onClose();
        }, o.closeDelay);
      }
    },
    openNow() {
      clearOpen();
      clearClose();
      if (!open) {
        open = true;
        o.onOpen();
      }
    },
    setPinned(p) {
      pinned = p;
    },
    notifyClosed() {
      open = false;
      pinned = false;
      clearOpen();
      clearClose();
    },
    dispose() {
      clearOpen();
      clearClose();
    },
  };
}
