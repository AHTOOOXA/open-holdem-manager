const { app, BrowserWindow, dialog, ipcMain, shell } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const net = require('net');
const http = require('http');
const https = require('https');

// Windows: electron-updater works without code signing (full auto-update).
// macOS: requires Apple Developer account ($99/yr) for code signing, so we
// fall back to GitHub API release checking with manual download.
// TODO: Buy Apple Developer account and enable autoUpdater on macOS too.
const isMac = process.platform === 'darwin';
const autoUpdater = !isMac ? require('electron-updater').autoUpdater : null;

let backendProcess = null;
let mainWindow = null;

const isDev = !app.isPackaged;

function findFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.listen(0, '127.0.0.1', () => {
      const port = server.address().port;
      server.close(() => resolve(port));
    });
    server.on('error', reject);
  });
}

function getResourcePath(...parts) {
  if (isDev) {
    return path.join(__dirname, '..', ...parts);
  }
  return path.join(process.resourcesPath, ...parts);
}

function startBackend(port) {
  if (isDev) {
    // In dev mode, backend is started separately (make dev / make backend)
    return Promise.resolve();
  }

  const backendExe = process.platform === 'win32'
    ? getResourcePath('backend', 'ohm-backend.exe')
    : getResourcePath('backend', 'ohm-backend');

  const dataDir = path.join(app.getPath('userData'), 'data');
  const staticDir = getResourcePath('frontend');

  const env = {
    ...process.env,
    OHM_DATA_DIR: dataDir,
    OHM_STATIC_DIR: staticDir,
  };

  return new Promise((resolve, reject) => {
    backendProcess = spawn(backendExe, ['--port', String(port)], {
      env,
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    backendProcess.stdout.on('data', (data) => {
      console.log(`[backend] ${data.toString().trim()}`);
    });

    backendProcess.stderr.on('data', (data) => {
      console.error(`[backend] ${data.toString().trim()}`);
    });

    backendProcess.on('error', (err) => {
      reject(new Error(`Failed to start backend: ${err.message}`));
    });

    backendProcess.on('exit', (code) => {
      if (code !== 0 && code !== null) {
        console.error(`Backend exited with code ${code}`);
      }
      backendProcess = null;
    });

    // Give the process a moment to fail on startup errors
    setTimeout(resolve, 200);
  });
}

function waitForBackend(url, maxRetries = 30) {
  return new Promise((resolve, reject) => {
    let attempts = 0;

    function tryConnect() {
      attempts++;
      const req = http.get(`${url}/api/health`, (res) => {
        if (res.statusCode === 200) {
          resolve();
        } else if (attempts < maxRetries) {
          setTimeout(tryConnect, 500);
        } else {
          reject(new Error(`Backend returned status ${res.statusCode}`));
        }
        res.resume(); // consume response
      });

      req.on('error', () => {
        if (attempts < maxRetries) {
          setTimeout(tryConnect, 500);
        } else {
          reject(new Error('Backend did not start in time'));
        }
      });

      req.setTimeout(2000, () => {
        req.destroy();
        if (attempts < maxRetries) {
          setTimeout(tryConnect, 500);
        } else {
          reject(new Error('Backend health check timed out'));
        }
      });
    }

    tryConnect();
  });
}

function createWindow(url) {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    title: 'Open Holdem Manager',
    backgroundColor: '#0c0a09',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  mainWindow.loadURL(url);

  if (isDev) {
    mainWindow.webContents.openDevTools();
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function killBackend() {
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
  }
}

// --- Update system ---
// Windows: electron-updater (full auto-update)
// macOS: GitHub API checker (manual download until we get Apple signing)

const REPO_OWNER = 'AHTOOOXA';
const REPO_NAME = 'open-holdem-manager';

let updateState = { available: null, downloaded: false };

// --- Windows: electron-updater auto-update ---

function setupAutoUpdater() {
  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true;

  autoUpdater.on('update-available', (info) => {
    updateState.available = { version: info.version, releaseNotes: info.releaseNotes };
    if (mainWindow) {
      mainWindow.webContents.send('update-available', updateState.available);
    }
  });

  autoUpdater.on('download-progress', (progress) => {
    if (mainWindow) {
      mainWindow.webContents.send('download-progress', { percent: progress.percent });
    }
  });

  autoUpdater.on('update-downloaded', () => {
    updateState.downloaded = true;
    if (mainWindow) {
      mainWindow.webContents.send('update-downloaded');
    }
  });

  autoUpdater.on('error', (err) => {
    console.error('Auto-updater error:', err.message);
    if (mainWindow) {
      mainWindow.webContents.send('update-error', err.message);
    }
  });

  autoUpdater.checkForUpdates().catch((err) => {
    console.error('Update check failed:', err.message);
  });

  setInterval(() => {
    autoUpdater.checkForUpdates().catch((err) => {
      console.error('Periodic update check failed:', err.message);
    });
  }, 4 * 60 * 60 * 1000);
}

// --- macOS: GitHub API release checker ---

function checkForGitHubUpdate() {
  return new Promise((resolve) => {
    const url = `https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/releases/latest`;
    https.get(url, { headers: { 'User-Agent': 'open-holdem-manager' } }, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          const release = JSON.parse(data);
          const latestVersion = (release.tag_name || '').replace(/^v/, '');
          const currentVersion = app.getVersion();
          if (latestVersion && latestVersion !== currentVersion && isNewer(latestVersion, currentVersion)) {
            const info = { version: latestVersion, releaseNotes: release.body || null };
            updateState.available = info;
            if (mainWindow) {
              mainWindow.webContents.send('update-available', info);
            }
          }
          resolve();
        } catch (err) {
          console.error('Failed to parse GitHub release:', err.message);
          resolve();
        }
      });
    }).on('error', (err) => {
      console.error('GitHub update check failed:', err.message);
      resolve();
    });
  });
}

function isNewer(latest, current) {
  const a = latest.split('.').map(Number);
  const b = current.split('.').map(Number);
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    if ((a[i] || 0) > (b[i] || 0)) return true;
    if ((a[i] || 0) < (b[i] || 0)) return false;
  }
  return false;
}

function setupGitHubChecker() {
  checkForGitHubUpdate();
  setInterval(() => checkForGitHubUpdate(), 4 * 60 * 60 * 1000);
}

// --- Unified setup ---

function setupUpdateSystem() {
  if (isDev) return;
  if (autoUpdater) {
    setupAutoUpdater();
  } else {
    setupGitHubChecker();
  }
}

// --- IPC handlers ---

ipcMain.handle('install-update', () => {
  if (!autoUpdater) return;
  setTimeout(() => {
    try {
      autoUpdater.quitAndInstall(false, true);
    } catch (err) {
      console.error('quitAndInstall failed:', err);
      app.relaunch();
      app.exit(0);
    }
  }, 100);
});

ipcMain.handle('get-app-version', () => app.getVersion());

ipcMain.handle('check-for-updates', () => {
  if (isDev) return;
  if (updateState.available && mainWindow) {
    mainWindow.webContents.send('update-available', updateState.available);
    if (updateState.downloaded) {
      mainWindow.webContents.send('update-downloaded');
    }
    return;
  }
  if (autoUpdater) {
    autoUpdater.checkForUpdates().catch((err) => {
      console.error('Manual update check failed:', err.message);
    });
  } else {
    checkForGitHubUpdate();
  }
});

ipcMain.handle('open-external', (_event, url) => {
  // Only allow GitHub URLs for safety
  if (typeof url === 'string' && url.startsWith('https://github.com/')) {
    shell.openExternal(url);
  }
});

app.whenReady().then(async () => {
  try {
    let url;

    if (isDev) {
      // Dev: Vite dev server should already be running
      url = 'http://localhost:5173';
    } else {
      // Production: start backend on a random free port
      const port = await findFreePort();
      await startBackend(port);
      url = `http://127.0.0.1:${port}`;
      await waitForBackend(url);
    }

    createWindow(url);
    setupUpdateSystem();
  } catch (err) {
    console.error('Startup error:', err);
    dialog.showErrorBox(
      'Open Holdem Manager - Startup Error',
      `Failed to start the application.\n\n${err.message}`
    );
    killBackend();
    app.quit();
  }
});

app.on('window-all-closed', () => {
  killBackend();
  app.quit();
});

app.on('before-quit', () => {
  killBackend();
});

// macOS: re-create window when dock icon clicked
app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0 && !isDev) {
    // Would need to track the port — for now just quit+relaunch
  }
});
