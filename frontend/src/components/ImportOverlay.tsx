/**
 * Import progress no longer blocks the screen: the status bar (and the welcome view for an empty
 * workspace) show it, and completion is reported via toasts (see ImportContext). What you import
 * is chosen in DragDropOverlay. Kept as a mount point for App.tsx.
 */
export default function ImportOverlay() {
  return null;
}
