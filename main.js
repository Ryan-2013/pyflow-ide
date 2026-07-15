'use strict';
/**
 * PyFlow IDE — Electron 主程序
 * 負責啟動 Python 後端（dev: python app.py, packaged: pyflow-server binary）
 * 並開啟瀏覽器視窗
 */
const { app, BrowserWindow, shell, ipcMain, dialog } = require('electron');
const { spawn }   = require('child_process');
const path        = require('path');
const net         = require('net');
const os          = require('os');
const fs          = require('fs');

const PORT        = process.env.PYFLOW_PORT || 5000;
const DEV_URL     = `http://localhost:${PORT}`;
const START_TIMEOUT = 90000;   // 低資源環境下 PyInstaller 後端首次解壓會比較久

let mainWindow    = null;
let serverProcess = null;

function logLaunch(message) {
  const line = `[${new Date().toISOString()}] ${message}\n`;
  console.log(line.trimEnd());
  if (app.isPackaged) {
    try {
      fs.appendFileSync(path.join(app.getPath('userData'), 'pyflow-launch.log'), line);
    } catch (_) {}
  }
}

// ── 找到 Python 後端可執行路徑 ─────────────────────────────────
function getServerCmd() {
  if (app.isPackaged) {
    // 打包模式：使用 PyInstaller 打包的二進位
    const ext  = process.platform === 'win32' ? '.exe' : '';
    const bin  = path.join(process.resourcesPath, 'server', `pyflow-server${ext}`);
    return { cmd: bin, args: ['--port', String(PORT)] };
  } else {
    // 開發模式：直接用 Python
    const python = process.platform === 'win32' ? 'python' : 'python3';
    const appPy  = path.join(__dirname, 'pyflow', 'app.py');
    return { cmd: python, args: [appPy, '--port', String(PORT)] };
  }
}

// ── 等待 port 可用 ─────────────────────────────────────────────
function waitForPort(port, timeout) {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + timeout;
    function tryConnect() {
      const sock = net.createConnection(port, '127.0.0.1');
      sock.on('connect', () => { sock.destroy(); resolve(); });
      sock.on('error', () => {
        if (Date.now() > deadline) return reject(new Error('Server timeout'));
        setTimeout(tryConnect, 300);
      });
    }
    tryConnect();
  });
}

// ── 啟動 Python 後端 ─────────────────────────────────────────────
function startServer() {
  const { cmd, args } = getServerCmd();
  const cwd = app.isPackaged ? process.resourcesPath : __dirname;
  logLaunch(`[PyFlow] Starting server: ${cmd} ${args.join(' ')}`);
  logLaunch(`[PyFlow] cwd=${cwd} PYFLOW_PORT=${PORT}`);

  serverProcess = spawn(cmd, args, {
    env: {
      ...process.env,
      PYFLOW_PORT: String(PORT),
      PYTHONUTF8: '1',
      PYTHONIOENCODING: 'utf-8',
    },
    cwd,
    windowsHide: true,
  });

  serverProcess.stdout?.on('data', d => logLaunch(`[server stdout] ${String(d).trimEnd()}`));
  serverProcess.stderr?.on('data', d => logLaunch(`[server stderr] ${String(d).trimEnd()}`));

  serverProcess.on('error', err => {
    logLaunch(`[PyFlow] Server error: ${err.stack || err.message}`);
    dialog.showErrorBox('啟動失敗',
      `無法啟動後端伺服器：\n${err.message}\n\n` +
      '請確認 Python 3.8+ 已安裝，或重新安裝 PyFlow IDE。');
    app.quit();
  });

  serverProcess.on('exit', (code, signal) => {
    logLaunch(`[PyFlow] Server exited: code=${code} signal=${signal}`);
    if (code !== 0 && mainWindow) {
      console.error(`[PyFlow] Server exited: code=${code} signal=${signal}`);
    }
  });
}

// ── 建立主視窗 ─────────────────────────────────────────────────
function createWindow() {
  const { width, height } = require('electron').screen.getPrimaryDisplay().workAreaSize;

  mainWindow = new BrowserWindow({
    width:           Math.min(1600, width  - 40),
    height:          Math.min(1000, height - 40),
    minWidth:        900,
    minHeight:       600,
    show:            false,
    backgroundColor: '#0a0a0a',
    titleBarStyle:   process.platform === 'darwin' ? 'hiddenInset' : 'default',
    title:           '⬡ PyFlow IDE',
    icon:            path.join(__dirname, 'assets', process.platform === 'win32' ? 'icon.ico' : 'icon.png'),
    webPreferences: {
      preload:             path.join(__dirname, 'preload.js'),
      contextIsolation:    true,
      nodeIntegration:     false,
      webSecurity:         true,
      allowRunningInsecureContent: false,
    },
  });

  // 載入 app
  mainWindow.loadURL(DEV_URL).catch(err => {
    console.error('[PyFlow] Load failed:', err.message);
  });

  // 載入完成後顯示
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    mainWindow.focus();
    if (!app.isPackaged) mainWindow.webContents.openDevTools({ mode: 'detach' });
  });

  // 外部連結用瀏覽器開啟
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http')) shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.on('closed', () => { mainWindow = null; });
}

// ── 啟動流程 ───────────────────────────────────────────────────
app.whenReady().then(async () => {
  startServer();

  // 等待後端就緒
  try {
    await waitForPort(PORT, START_TIMEOUT);
    console.log(`[PyFlow] Server ready on port ${PORT}`);
    createWindow();
  } catch(err) {
    dialog.showErrorBox('啟動逾時',
      `後端伺服器在 ${START_TIMEOUT/1000} 秒內未啟動。\n\n` +
      '請檢查防火牆設定或以管理員身份執行。');
    app.quit();
  }
});

// ── macOS 重新開啟 ─────────────────────────────────────────────
app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

// ── 關閉時停止後端 ─────────────────────────────────────────────
app.on('before-quit', () => {
  if (serverProcess) {
    serverProcess.kill('SIGTERM');
    serverProcess = null;
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

function configPath() {
  return path.join(app.getPath('userData'), 'config.json');
}

async function readConfig() {
  try {
    return JSON.parse(await fs.promises.readFile(configPath(), 'utf8'));
  } catch (_) {
    return {};
  }
}

async function writeConfig(patch) {
  const next = { ...(await readConfig()), ...(patch || {}) };
  await fs.promises.mkdir(path.dirname(configPath()), { recursive: true });
  await fs.promises.writeFile(configPath(), JSON.stringify(next, null, 2), 'utf8');
  return next;
}

function normalizeDialogPath(result) {
  if (result.canceled || !result.filePaths?.length) return null;
  return result.filePaths[0];
}

// ── IPC: renderer bridge ───────────────────────────────────────
ipcMain.handle('open-external', (_, url) => shell.openExternal(url));
ipcMain.handle('get-app-version', () => app.getVersion());
ipcMain.handle('get:port', () => Number(PORT));
ipcMain.handle('get:platform', () => process.platform);
ipcMain.handle('get:config', () => readConfig());
ipcMain.handle('set:config', (_, patch) => writeConfig(patch));

ipcMain.handle('window:setTitle', (_, title) => {
  if (mainWindow && typeof title === 'string') {
    mainWindow.setTitle(title);
  }
  return true;
});

ipcMain.handle('dialog:openFolder', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: 'Open Folder',
    properties: ['openDirectory'],
  });
  return normalizeDialogPath(result);
});

ipcMain.handle('dialog:openFile', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: 'Open File',
    properties: ['openFile'],
  });
  return normalizeDialogPath(result);
});

ipcMain.handle('dialog:save', async (_, defaultPath) => {
  const result = await dialog.showSaveDialog(mainWindow, {
    defaultPath: defaultPath || undefined,
  });
  if (result.canceled || !result.filePath) return null;
  return result.filePath;
});

ipcMain.handle('dialog:confirm', async (_, message) => {
  const result = await dialog.showMessageBox(mainWindow, {
    type: 'question',
    buttons: ['Cancel', 'OK'],
    defaultId: 1,
    cancelId: 0,
    message: String(message || 'Continue?'),
  });
  return result.response === 1;
});

ipcMain.handle('fs:readFile', async (_, filePath) => {
  return fs.promises.readFile(filePath, 'utf8');
});

ipcMain.handle('fs:writeFile', async (_, filePath, content) => {
  await fs.promises.mkdir(path.dirname(filePath), { recursive: true });
  await fs.promises.writeFile(filePath, content ?? '', 'utf8');
  return true;
});

ipcMain.handle('fs:readDir', async (_, dirPath) => {
  const names = await fs.promises.readdir(dirPath);
  const entries = await Promise.all(names.map(async name => {
    const full = path.join(dirPath, name);
    const stat = await fs.promises.stat(full);
    return {
      name,
      path: full,
      type: stat.isDirectory() ? 'dir' : 'file',
      size: stat.isDirectory() ? 0 : stat.size,
      is_python: /\.(py|pyw)$/i.test(name),
    };
  }));
  return entries.sort((a, b) => {
    if (a.type !== b.type) return a.type === 'dir' ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
});

ipcMain.handle('fs:exists', async (_, targetPath) => fs.existsSync(targetPath));

ipcMain.handle('fs:showInFinder', async (_, targetPath) => {
  if (targetPath) shell.showItemInFolder(targetPath);
  return true;
});

ipcMain.handle('fs:mkdirp', async (_, dirPath) => {
  await fs.promises.mkdir(dirPath, { recursive: true });
  return true;
});
