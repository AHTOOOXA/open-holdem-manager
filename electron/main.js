const { app, BrowserWindow, dialog } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const net = require('net');
const http = require('http');

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
