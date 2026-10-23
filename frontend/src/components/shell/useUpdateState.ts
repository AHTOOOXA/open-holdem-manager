import { useEffect, useState } from 'react';
import { getElectronAPI } from '@/lib/electron';

export interface UpdateState {
  /** Version on offer, null when there is no update. */
  version: string | null;
  releaseNotes: string | null;
  /** Download progress 0..100 while downloading (Windows only). */
  percent: number | null;
  /** Downloaded and ready to install (Windows only). */
  ready: boolean;
  error: string | null;
  /** Windows gets in-app download + restart; macOS and Linux get a download link. */
  canAutoUpdate: boolean;
  /** The user hid the notice for this update. */
  dismissed: boolean;
  dismiss: () => void;
  startDownload: () => void;
}

/** Tells other screens (Configuration → Updates) about the update state. */
function dispatchUpdateState(state: { version: string; ready: boolean }) {
  window.dispatchEvent(new CustomEvent('ohm-update-state', { detail: state }));
}

/**
 * Subscribes to the Electron auto-updater once. Mount it in a component that never unmounts
 * (the status bar): the preload bridge has no way to unsubscribe.
 */
export function useUpdateState(): UpdateState {
  const [version, setVersion] = useState<string | null>(null);
  const [releaseNotes, setReleaseNotes] = useState<string | null>(null);
  const [percent, setPercent] = useState<number | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState(false);

  // TODO: Buy Apple Developer account ($99/yr) to enable auto-update on macOS
  const canAutoUpdate = getElectronAPI()?.platform === 'win32';

  useEffect(() => {
    const api = getElectronAPI();
    if (!api?.onUpdateAvailable) return;

    api.onUpdateAvailable((info) => {
      setVersion(info.version);
      setDismissed(false);
      if (typeof info.releaseNotes === 'string') setReleaseNotes(info.releaseNotes);
      dispatchUpdateState({ version: info.version, ready: false });
    });

    // These only fire on Windows (electron-updater)
    api.onDownloadProgress?.((info) => setPercent(Math.round(info.percent)));

    api.onUpdateDownloaded?.(() => {
      setReady(true);
      setPercent(null);
      setDismissed(false);
      setVersion((v) => {
        if (v) dispatchUpdateState({ version: v, ready: true });
        return v;
      });
    });

    api.onUpdateError?.((message) => setError(message));
  }, []);

  return {
    version,
    releaseNotes,
    percent,
    ready,
    error,
    canAutoUpdate,
    dismissed,
    dismiss: () => setDismissed(true),
    startDownload: () => {
      setPercent(0);
      getElectronAPI()?.downloadUpdate?.();
    },
  };
}
