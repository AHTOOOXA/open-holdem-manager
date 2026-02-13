import { useState, useEffect } from 'react';
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { X, ExternalLink } from 'lucide-react';

const REPO_URL = 'https://github.com/AHTOOOXA/open-holdem-manager';

interface ElectronAPI {
  platform: string;
  onUpdateAvailable: (cb: (info: { version: string; releaseNotes?: string }) => void) => void;
  onDownloadProgress: (cb: (info: { percent: number }) => void) => void;
  onUpdateDownloaded: (cb: () => void) => void;
  onUpdateError: (cb: (message: string) => void) => void;
  installUpdate: () => void;
  checkForUpdates: () => void;
  openExternal: (url: string) => void;
}

function getAPI(): ElectronAPI | null {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const api = (window as any).electronAPI as ElectronAPI | undefined;
  if (api?.onUpdateAvailable) return api;
  return null;
}

// Custom events so Settings dropdown can react to update state
export function dispatchUpdateState(state: { version: string; ready: boolean }) {
  window.dispatchEvent(new CustomEvent('ohm-update-state', { detail: state }));
}

export default function UpdateBanner() {
  const [version, setVersion] = useState<string | null>(null);
  const [releaseNotes, setReleaseNotes] = useState<string | null>(null);
  const [percent, setPercent] = useState<number | null>(null);
  const [ready, setReady] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [showNotes, setShowNotes] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Windows gets full auto-update; macOS gets manual download link
  // TODO: Buy Apple Developer account ($99/yr) to enable auto-update on macOS
  const canAutoUpdate = getAPI()?.platform === 'win32';

  useEffect(() => {
    const api = getAPI();
    if (!api) return;

    api.onUpdateAvailable((info) => {
      setVersion(info.version);
      setDismissed(false);
      if (typeof info.releaseNotes === 'string') {
        setReleaseNotes(info.releaseNotes);
      }
      dispatchUpdateState({ version: info.version, ready: false });
    });

    // These only fire on Windows (electron-updater)
    api.onDownloadProgress((info) => {
      setPercent(Math.round(info.percent));
    });

    api.onUpdateDownloaded(() => {
      setReady(true);
      setPercent(null);
      setDismissed(false);
      setVersion((v) => {
        if (v) dispatchUpdateState({ version: v, ready: true });
        return v;
      });
    });

    api.onUpdateError((message) => {
      setError(message);
    });
  }, []);

  if (!version || dismissed) return null;

  const releaseUrl = `${REPO_URL}/releases/tag/v${version}`;

  const renderContent = () => {
    // macOS: always show simple download link
    if (!canAutoUpdate) {
      return (
        <>
          <span className="shrink-0">Update v{version} available</span>
          {releaseNotes && (
            <button
              className="shrink-0 text-primary hover:underline"
              onClick={() => setShowNotes(true)}
            >
              What's new?
            </button>
          )}
          <Button
            size="sm"
            variant="outline"
            className="h-5 px-2 text-xs"
            onClick={() => getAPI()?.openExternal(releaseUrl)}
          >
            Download
          </Button>
        </>
      );
    }

    // Windows: full auto-update flow
    if (error) {
      return (
        <>
          <span className="min-w-0 truncate text-red">Update failed</span>
          <Button
            size="sm"
            variant="outline"
            className="h-5 shrink-0 px-2 text-xs"
            onClick={() => getAPI()?.openExternal(`${REPO_URL}/releases/latest`)}
          >
            Download manually
          </Button>
        </>
      );
    }

    if (ready) {
      return (
        <>
          <span className="shrink-0">Update v{version} ready</span>
          {releaseNotes && (
            <button
              className="shrink-0 text-primary hover:underline"
              onClick={() => setShowNotes(true)}
            >
              What's new?
            </button>
          )}
          <Button
            size="sm"
            variant="default"
            className="h-5 px-2 text-xs"
            onClick={() => getAPI()?.installUpdate()}
          >
            Restart to update
          </Button>
        </>
      );
    }

    if (percent != null) {
      return (
        <>
          <span className="shrink-0">Downloading v{version}...</span>
          <Progress value={percent} className="h-1.5 max-w-48" />
          <span className="shrink-0 tabular-nums">{percent}%</span>
        </>
      );
    }

    return (
      <>
        <span className="shrink-0">Update available: v{version}</span>
        {releaseNotes && (
          <button
            className="shrink-0 text-primary hover:underline"
            onClick={() => setShowNotes(true)}
          >
            What's new?
          </button>
        )}
      </>
    );
  };

  return (
    <>
      <div className="sticky bottom-0 flex items-center gap-3 border-t border-border bg-surface px-4 py-1.5 text-xs text-muted-foreground">
        {renderContent()}
        <button
          className="ml-auto shrink-0 text-muted-foreground hover:text-foreground"
          onClick={() => setDismissed(true)}
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      <Dialog open={showNotes} onOpenChange={setShowNotes}>
        <DialogContent className="max-w-lg max-h-[70vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>What's new in v{version}</DialogTitle>
            <DialogDescription asChild>
              <div
                className="pt-2 text-sm text-muted-foreground [&_h1]:text-base [&_h1]:font-semibold [&_h1]:text-foreground [&_h1]:mb-2 [&_h2]:text-sm [&_h2]:font-semibold [&_h2]:text-foreground [&_h2]:mb-2 [&_ul]:list-disc [&_ul]:pl-4 [&_ul]:space-y-1 [&_li]:leading-relaxed [&_p]:mb-2"
                dangerouslySetInnerHTML={{ __html: releaseNotes || '' }}
              />
            </DialogDescription>
          </DialogHeader>
          <div className="flex items-center gap-3 pt-2">
            <Button
              variant="outline"
              size="sm"
              className="gap-1.5"
              onClick={() => getAPI()?.openExternal(releaseUrl)}
            >
              <ExternalLink className="h-3.5 w-3.5" />
              View on GitHub
            </Button>
            {ready && canAutoUpdate && (
              <Button size="sm" onClick={() => getAPI()?.installUpdate()}>
                Restart to update
              </Button>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
