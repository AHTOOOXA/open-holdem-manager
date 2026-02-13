const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  platform: process.platform,
  isElectron: true,

  // App info
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),
  openExternal: (url) => ipcRenderer.invoke('open-external', url),

  // Update checker (GitHub-based, manual download)
  // TODO: Buy Apple Developer account ($99/yr) and re-enable electron-updater
  // IPC channels (onDownloadProgress, onUpdateDownloaded, installUpdate) for
  // true auto-update. See git history for the full implementation.
  onUpdateAvailable: (callback) => {
    ipcRenderer.on('update-available', (_event, info) => callback(info));
  },
  checkForUpdates: () => ipcRenderer.invoke('check-for-updates'),
});
