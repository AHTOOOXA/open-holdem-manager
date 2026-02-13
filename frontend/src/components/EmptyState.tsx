import { FolderUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useImport } from '@/contexts/ImportContext';

interface EmptyStateProps {
  variant: 'no-data' | 'no-match';
  onClearFilters?: () => void;
  message?: string;
}

export default function EmptyState({ variant, onClearFilters, message }: EmptyStateProps) {
  const { setShowImportOverlay } = useImport();

  if (variant === 'no-data') {
    return (
      <div className="text-center py-12">
        <FolderUp className="mx-auto mb-3 text-text-muted" size={40} strokeWidth={1.5} />
        <p className="text-text-muted text-lg">{message ?? 'No hands imported yet'}</p>
        <p className="text-text-muted text-sm mt-1">Import hand history files or drag & drop anywhere.</p>
        <Button
          variant="outline"
          size="sm"
          className="mt-4"
          onClick={() => setShowImportOverlay(true)}
        >
          <FolderUp className="mr-2 h-4 w-4" />
          Import Hands
        </Button>
      </div>
    );
  }

  return (
    <div className="text-center py-12">
      <p className="text-text-muted text-lg">{message ?? 'No hands match the selected filters.'}</p>
      <p className="text-text-muted text-sm mt-1">Try adjusting your filters or import more hand histories.</p>
      {onClearFilters && (
        <Button variant="link" onClick={onClearFilters} className="mt-2 text-sm">
          Clear filters
        </Button>
      )}
    </div>
  );
}
