/** The bridge `electron/preload.js` exposes as `window.electronAPI` (absent in the browser). */
export interface ElectronAPI {
  platform: string;
  isElectron?: boolean;
  getAppVersion?: () => Promise<string>;
  openExternal?: (url: string) => void;
  onUpdateAvailable?: (cb: (info: { version: string; releaseNotes?: string }) => void) => void;
  onDownloadProgress?: (cb: (info: { percent: number }) => void) => void;
  onUpdateDownloaded?: (cb: () => void) => void;
  onUpdateError?: (cb: (message: string) => void) => void;
  downloadUpdate?: () => void;
  installUpdate?: () => void;
  checkForUpdates?: () => void;
}

export const REPO_URL = 'https://github.com/AHTOOOXA/open-holdem-manager';

export function getElectronAPI(): ElectronAPI | null {
  return (window as unknown as { electronAPI?: ElectronAPI }).electronAPI ?? null;
}

/** Opens a URL in the system browser (Electron) or a new tab (web). */
export function openExternal(url: string): void {
  const api = getElectronAPI();
  if (api?.openExternal) api.openExternal(url);
  else window.open(url, '_blank', 'noopener,noreferrer');
}
