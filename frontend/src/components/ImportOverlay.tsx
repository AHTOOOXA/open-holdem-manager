import ImportFromDatabaseDialog from '@/components/import/ImportFromDatabaseDialog';
import ImportHandHistoryDialog from '@/components/import/ImportHandHistoryDialog';

/**
 * Import progress does not block the screen: the status bar (and the welcome view for an empty
 * workspace) show it, and completion is reported via toasts (see ImportContext). What you import
 * is chosen in DragDropOverlay. This is the mount point of the two import dialogs: "Import From
 * Database" and the "Import Hand History" step every manual import goes through.
 */
export default function ImportOverlay() {
  return (
    <>
      <ImportFromDatabaseDialog />
      <ImportHandHistoryDialog />
    </>
  );
}
