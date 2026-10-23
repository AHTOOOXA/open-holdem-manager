import { useState } from 'react';
import { ExternalLink, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { REPO_URL, getElectronAPI, openExternal } from '@/lib/electron';
import type { UpdateState } from './useUpdateState';

/** The update-available line in the status bar, with its actions and the release notes dialog. */
export default function UpdateNotice({ update }: { update: UpdateState }) {
  const [showNotes, setShowNotes] = useState(false);
  const { version, releaseNotes, percent, ready, error, canAutoUpdate } = update;
  if (!version) return null;

  const releaseUrl = `${REPO_URL}/releases/tag/v${version}`;
  const notesButton = releaseNotes ? (
    <button
      type="button"
      className="shrink-0 rounded-control text-primary outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring"
      onClick={() => setShowNotes(true)}
    >
      What's new?
    </button>
  ) : null;

  let content;
  if (!canAutoUpdate) {
    // macOS / Linux: manual download
    content = (
      <>
        <span className="shrink-0">Update v{version} available</span>
        {notesButton}
        <Button size="xs" variant="outline" className="h-5" onClick={() => openExternal(releaseUrl)}>
          Download
        </Button>
      </>
    );
  } else if (error) {
    content = (
      <>
        <span className="min-w-0 truncate text-destructive">Update failed</span>
        <Button
          size="xs"
          variant="outline"
          className="h-5"
          onClick={() => openExternal(`${REPO_URL}/releases/latest`)}
        >
          Download manually
        </Button>
      </>
    );
  } else if (ready) {
    content = (
      <>
        <span className="shrink-0">Update v{version} ready</span>
        {notesButton}
        <Button size="xs" className="h-5" onClick={() => getElectronAPI()?.installUpdate?.()}>
          Restart to update
        </Button>
      </>
    );
  } else if (percent != null) {
    content = (
      <>
        <span className="shrink-0">Downloading v{version}…</span>
        <Progress value={percent} className="h-1 w-32" aria-label="Update download" />
        <span className="shrink-0 tabular-nums">{percent}%</span>
      </>
    );
  } else {
    content = (
      <>
        <span className="shrink-0">Update available: v{version}</span>
        {notesButton}
        <Button size="xs" variant="outline" className="h-5" onClick={update.startDownload}>
          Download
        </Button>
      </>
    );
  }

  return (
    <>
      <div className="flex min-w-0 items-center gap-2">
        {content}
        <button
          type="button"
          className="shrink-0 rounded-control p-0.5 text-muted-foreground outline-none hover:bg-overlay-hover hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
          onClick={update.dismiss}
          aria-label="Hide update notice"
        >
          <X className="size-3.5" />
        </button>
      </div>

      <Dialog open={showNotes} onOpenChange={setShowNotes}>
        <DialogContent className="max-h-[70vh] max-w-lg overflow-y-auto">
          <DialogHeader>
            <DialogTitle>What's new in v{version}</DialogTitle>
            <DialogDescription asChild>
              <div
                className="pt-2 text-sm text-muted-foreground [&_h1]:mb-2 [&_h1]:text-base [&_h1]:font-semibold [&_h1]:text-foreground [&_h2]:mb-2 [&_h2]:text-sm [&_h2]:font-semibold [&_h2]:text-foreground [&_li]:leading-relaxed [&_p]:mb-2 [&_ul]:list-disc [&_ul]:space-y-1 [&_ul]:pl-4"
                dangerouslySetInnerHTML={{ __html: releaseNotes || '' }}
              />
            </DialogDescription>
          </DialogHeader>
          <div className="flex items-center gap-3 pt-2">
            <Button variant="outline" size="sm" className="gap-1.5" onClick={() => openExternal(releaseUrl)}>
              <ExternalLink className="size-3.5" />
              View on GitHub
            </Button>
            {ready && canAutoUpdate && (
              <Button size="sm" onClick={() => getElectronAPI()?.installUpdate?.()}>
                Restart to update
              </Button>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
