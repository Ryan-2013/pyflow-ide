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

const PORT        = process.env.PYFLOW_PORT || 5000;
const DEV_URL     = `http://localhost:${PORT}`;
const START_TIMEOUT = 30000;   // 30 秒等待後端啟動

let mainWindow    = null;
let serverProcess = null;

// ── 找到 Python 後端可執行路徑 ─────────────────────────────────
function getServerCmd() {
  if (app.isPackaged) {
    // 打包模式：使用 PyInstaller 打包的二進位
    const ext  = process.platform === 'win32' ? '.exe' : '';
    const bin  = path.join(process.resourcesPath, 'server', `pyflow-server${ext}`);
    return { cmd: bin, args: [] };
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
  console.log(`[PyFlow] Starting server: ${cmd} ${args.join(' ')}`);

  serverProcess = spawn(cmd, args, {
    env: { ...process.env, PYFLOW_PORT: String(PORT) },
    cwd: app.isPackaged ? process.resourcesPath : __dirname,
  });

  serverProcess.stdout?.on('data', d => process.stdout.write(`[server] ${d}`));
  serverProcess.stderr?.on('data', d => process.stderr.write(`[server] ${d}`));

  serverProcess.on('error', err => {
    dialog.showErrorBox('啟動失敗',
      `無法啟動後端伺服器：\n${err.message}\n\n` +
      '請確認 Python 3.8+ 已安裝，或重新安裝 PyFlow IDE。');
    app.quit();
  });

  serverProcess.on('exit', (code, signal) => {
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

// ── IPC: 開啟外部連結 ──────────────────────────────────────────
ipcMain.handle('open-external', (_, url) => shell.openExternal(url));
ipcMain.handle('get-app-version', () => app.getVersion());
