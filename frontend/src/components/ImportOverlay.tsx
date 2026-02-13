import { useImport } from '@/contexts/ImportContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';

export default function ImportOverlay() {
  const { phase, fileInfo, progress, result, error, dismiss } = useImport();

  if (phase === 'idle' || phase === 'rebuilding') return null;

  const pct =
    progress?.total != null && progress.total > 0
      ? Math.round(((progress.processed ?? 0) / progress.total) * 100)
      : 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
      <Card className="w-full max-w-md mx-4">
        {/* Uploading */}
        {phase === 'uploading' && (
          <>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Importing Hands...</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {progress?.type === 'start' || progress?.type === 'progress' ? (
                <>
                  <p className="text-text-muted text-sm">
                    {fileInfo && !progress?.total_hands
                      ? `Uploading ${fileInfo.count} file${fileInfo.count !== 1 ? 's' : ''} (${(fileInfo.size / 1024).toFixed(0)} KB)...`
                      : `Processing ${progress?.total_hands?.toLocaleString() ?? '...'} hands from ${progress?.files ?? fileInfo?.count ?? '?'} file${(progress?.files ?? fileInfo?.count ?? 0) !== 1 ? 's' : ''}...`}
                  </p>
                  {progress?.total != null && progress.total > 0 && (
                    <>
                      <Progress value={pct} className="h-2" />
                      <div className="flex justify-between text-xs text-text-muted">
                        <span>
                          {(progress.processed ?? 0).toLocaleString()} / {progress.total.toLocaleString()}
                        </span>
                        <span>{pct}%</span>
                      </div>
                      <div className="flex gap-4 justify-center text-xs">
                        <span className="text-green">{(progress.imported ?? 0).toLocaleString()} imported</span>
                        <span className="text-yellow">{(progress.duplicates ?? 0).toLocaleString()} duplicates</span>
                        {(progress.errors ?? 0) > 0 && (
                          <span className="text-red">{(progress.errors ?? 0).toLocaleString()} errors</span>
                        )}
                        {(progress.hands_per_sec ?? 0) > 0 && (
                          <span className="text-text-muted">{progress.hands_per_sec?.toLocaleString()} h/s</span>
                        )}
                      </div>
                    </>
                  )}
                </>
              ) : (
                <p className="text-text-muted text-sm">
                  {fileInfo
                    ? `Uploading ${fileInfo.count} file${fileInfo.count !== 1 ? 's' : ''} (${(fileInfo.size / 1024).toFixed(0)} KB)...`
                    : 'Uploading...'}
                </p>
              )}
            </CardContent>
          </>
        )}

        {/* Done */}
        {phase === 'done' && result && (
          <>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Import Complete</CardTitle>
              {result.elapsed_ms != null && result.imported > 0 && (
                <p className="text-sm text-text-muted">
                  {result.imported.toLocaleString()} hands in {(result.elapsed_ms / 1000).toFixed(1)}s
                  ({result.hands_per_sec?.toLocaleString()} h/s)
                </p>
              )}
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <div className="text-2xl font-bold text-green">{result.imported}</div>
                  <div className="text-xs text-text-muted">Imported</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-yellow">{result.duplicates}</div>
                  <div className="text-xs text-text-muted">Duplicates</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-red">{result.errors}</div>
                  <div className="text-xs text-text-muted">Errors</div>
                </div>
              </div>
              {result.parse_ms != null && result.imported > 0 && (
                <div className="text-xs text-text-muted text-center">
                  parse {result.parse_ms}ms / stats {result.stats_ms}ms / equity {result.equity_ms ?? 0}ms / db {result.db_ms}ms
                </div>
              )}
              {result.error_details.length > 0 && (
                <div className="text-xs text-red space-y-1">
                  {result.error_details.map((e, i) => (
                    <div key={i}>{e}</div>
                  ))}
                </div>
              )}
              <Button className="w-full" onClick={dismiss}>
                Done
              </Button>
            </CardContent>
          </>
        )}

        {/* Error */}
        {phase === 'error' && (
          <CardContent className="space-y-3 pt-6">
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
            <Button className="w-full" variant="outline" onClick={dismiss}>
              Close
            </Button>
          </CardContent>
        )}
      </Card>
    </div>
  );
}
