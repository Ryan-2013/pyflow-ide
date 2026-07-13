'use strict';
const { app, BrowserWindow, ipcMain, dialog, Menu, shell, nativeTheme } = require('electron');
const { spawn, execFileSync }  = require('child_process');
const path = require('path');
const fs   = require('fs');
const net  = require('net');
const os   = require('os');

// ── Config persistence ──────────────────────────────────────────
const CONFIG_PATH = path.join(app.getPath('userData'), 'config.json');
let config = { recent: [], windowBounds: null };
try { config = { ...config, ...JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8')) }; } catch {}
function saveConfig() { try { fs.writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2)); } catch {} }

// ── State ───────────────────────────────────────────────────────
let mainWin = null;
let flask   = null;
let flaskPort = 5000;
let pythonPath = null;
let isQuitting = false;

// ── Python detection ────────────────────────────────────────────
function findPython() {
  const cands = process.platform === 'win32'
    ? ['python3', 'python', 'py']
    : ['python3', 'python3.12', 'python3.11', 'python3.10', 'python3.9', 'python'];
  for (const py of cands) {
    try {
      const v = execFileSync(py, ['--version'], { encoding: 'utf8', timeout: 4000, windowsHide: true });
      const m = v.match(/Python\s+(\d+)\.(\d+)/);
      if (m && parseInt(m[1]) === 3 && parseInt(m[2]) >= 9) return py;
    } catch {}
  }
  return null;
}

// ── Port helpers ─────────────────────────────────────────────────
function findFreePort(start = 5000) {
  return new Promise(res => {
    const s = net.createServer();
    s.on('error', () => res(findFreePort(start + 1)));
    s.listen(start, () => s.close(() => res(start)));
  });
}

function waitForPort(port, ms = 18000) {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + ms;
    (function try_() {
      const s = net.createConnection(port, '127.0.0.1');
      s.once('connect', () => { s.destroy(); resolve(); });
      s.once('error', () => {
        if (Date.now() > deadline) return reject(new Error(`Flask 啟動逾時 (port ${port})`));
        setTimeout(try_, 250);
      });
    })();
  });
}

// ── Flask management ─────────────────────────────────────────────
async function startFlask() {
  flaskPort = await findFreePort();
  const pyflowDir = app.isPackaged
    ? path.join(process.resourcesPath, 'pyflow')
    : path.join(__dirname, 'pyflow');

  // Auto-install requirements (silent, skip if already ok)
  try {
    execFileSync(pythonPath, ['-c', 'import flask, flask_socketio, eventlet'], { timeout: 5000, windowsHide: true });
  } catch {
    try {
      execFileSync(pythonPath, ['-m', 'pip', 'install', '-q', '-r', path.join(pyflowDir, 'requirements.txt')],
        { timeout: 60000, windowsHide: true, stdio: 'pipe' });
    } catch (e) { console.error('pip install failed:', e.message); }
  }

  flask = spawn(pythonPath, ['-u', path.join(pyflowDir, 'app.py'), '--port', String(flaskPort)], {
    cwd: pyflowDir,
    windowsHide: true,
    env: {
      ...process.env,
      PYTHONUNBUFFERED: '1',
      PYFLOW_PORT: String(flaskPort),
      PYFLOW_START_DIR: os.homedir(),
    },
  });

  flask.stdout.on('data', d => process.stdout.write('[Flask] ' + d));
  flask.stderr.on('data', d => process.stderr.write('[Flask] ' + d));
  flask.on('exit', (code) => {
    if (!isQuitting && code !== 0 && code !== null) {
      dialog.showErrorBox('PyFlow 伺服器崩潰', `Flask 意外停止 (code ${code})\n請重新啟動應用程式。`);
    }
  });
}

// ── Window ───────────────────────────────────────────────────────
function createWindow() {
  const { width = 1440, height = 920, x, y } = config.windowBounds || {};
  mainWin = new BrowserWindow({
    width, height, x, y,
    minWidth: 900, minHeight: 600,
    backgroundColor: '#1a1625',
    show: false,
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      spellcheck: false,
    },
  });

  mainWin.loadURL(`http://localhost:${flaskPort}`);

  mainWin.once('ready-to-show', () => {
    mainWin.show();
    if (process.env.NODE_ENV === 'development') mainWin.webContents.openDevTools();
  });

  // Persist window state
  mainWin.on('close', () => {
    config.windowBounds = mainWin.getBounds();
    saveConfig();
  });
  mainWin.on('closed', () => { mainWin = null; });

  // Open external links in browser
  mainWin.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
}

// ── Native Menus ─────────────────────────────────────────────────
function buildMenu() {
  const send = cmd => mainWin?.webContents.send('menu', cmd);
  const T = [
    {
      label: '檔案',
      submenu: [
        { label: '開啟資料夾…', accelerator: 'CmdOrCtrl+Shift+O', click: () => send('openFolder') },
        { label: '開啟檔案…',   accelerator: 'CmdOrCtrl+O',       click: () => send('openFile')   },
        { type: 'separator' },
        { label: '新增 Python 檔案', accelerator: 'CmdOrCtrl+N',  click: () => send('newFile')    },
        { type: 'separator' },
        { label: '儲存',           accelerator: 'CmdOrCtrl+S',       click: () => send('save')       },
        { label: '另存新檔…',      accelerator: 'CmdOrCtrl+Shift+S', click: () => send('saveAs')     },
        { type: 'separator' },
        { label: '關閉標籤',       accelerator: 'CmdOrCtrl+W',       click: () => send('closeTab')   },
        { label: '關閉全部',       click: () => send('closeAll')   },
        { type: 'separator' },
        process.platform === 'darwin'
          ? { label: '結束 PyFlow', role: 'quit' }
          : { label: '結束', accelerator: 'Alt+F4', role: 'quit' },
      ],
    },
    {
      label: '編輯',
      submenu: [
        { label: '復原',     role: 'undo' },
        { label: '取消復原', role: 'redo' },
        { type: 'separator' },
        { label: '剪下',     role: 'cut'       },
        { label: '複製',     role: 'copy'      },
        { label: '貼上',     role: 'paste'     },
        { label: '全選',     role: 'selectAll' },
        { type: 'separator' },
        { label: '尋找…',   accelerator: 'CmdOrCtrl+F', click: () => send('find') },
        { label: '取代…',   accelerator: 'CmdOrCtrl+H', click: () => send('replace') },
        { label: '跳至行…', accelerator: 'CmdOrCtrl+G', click: () => send('goToLine') },
      ],
    },
    {
      label: '視圖',
      submenu: [
        { label: '切換側邊欄',   accelerator: 'CmdOrCtrl+B',        click: () => send('toggleSidebar')  },
        { label: '切換終端機',   accelerator: 'Ctrl+`',              click: () => send('toggleTerminal') },
        { label: '切換迷你地圖', accelerator: 'CmdOrCtrl+Shift+M',  click: () => send('toggleMinimap')  },
        { type: 'separator' },
        { label: '⚡ 重新分析', accelerator: 'CmdOrCtrl+Shift+A',   click: () => send('analyze') },
        { label: '流程圖適應畫面', accelerator: 'CmdOrCtrl+Shift+F', click: () => send('fitView') },
        { label: '搜尋節點…',   accelerator: 'CmdOrCtrl+Shift+P',   click: () => send('searchNode') },
        { type: 'separator' },
        { label: '放大', role: 'zoomIn'    },
        { label: '縮小', role: 'zoomOut'   },
        { label: '重設', role: 'resetZoom' },
        { type: 'separator' },
        { label: '全螢幕', role: 'togglefullscreen' },
      ],
    },
    {
      label: '執行',
      submenu: [
        { label: '▶ 執行目前檔案', accelerator: 'F5',       click: () => send('run')  },
        { label: '⏹ 停止',        accelerator: 'Shift+F5', click: () => send('stop') },
        { type: 'separator' },
        { label: '在終端機中開啟資料夾', click: () => send('openFolderInTerminal') },
      ],
    },
  ];

  if (process.platform === 'darwin') {
    T.unshift({
      label: app.name,
      submenu: [
        { role: 'about' }, { type: 'separator' },
        { role: 'services' }, { type: 'separator' },
        { role: 'hide' }, { role: 'hideOthers' }, { role: 'unhide' },
        { type: 'separator' }, { role: 'quit' },
      ],
    });
  }
  Menu.setApplicationMenu(Menu.buildFromTemplate(T));
}

// ── IPC handlers ─────────────────────────────────────────────────
ipcMain.handle('get:port',     () => flaskPort);
ipcMain.handle('get:config',   () => config);
ipcMain.handle('set:config',   (_, patch) => { Object.assign(config, patch); saveConfig(); });
ipcMain.handle('get:platform', () => process.platform);

ipcMain.handle('dialog:openFolder', async () => {
  const r = await dialog.showOpenDialog(mainWin, { properties: ['openDirectory'], title: '開啟資料夾' });
  return r.canceled ? null : r.filePaths[0];
});
ipcMain.handle('dialog:openFile', async () => {
  const r = await dialog.showOpenDialog(mainWin, {
    properties: ['openFile', 'multiSelections'],
    filters: [{ name: 'Python', extensions: ['py', 'pyw'] }, { name: '全部', extensions: ['*'] }],
  });
  return r.canceled ? [] : r.filePaths;
});
ipcMain.handle('dialog:save', async (_, defaultPath) => {
  const r = await dialog.showSaveDialog(mainWin, {
    defaultPath,
    filters: [{ name: 'Python', extensions: ['py', 'pyw'] }, { name: '全部', extensions: ['*'] }],
  });
  return r.canceled ? null : r.filePath;
});
ipcMain.handle('dialog:confirm', async (_, msg) => {
  const r = await dialog.showMessageBox(mainWin, {
    type: 'question', buttons: ['儲存', '不儲存', '取消'],
    defaultId: 0, cancelId: 2, message: msg,
  });
  return r.response; // 0=save, 1=discard, 2=cancel
});

ipcMain.handle('fs:readFile',  (_, p)    => fs.readFileSync(p, 'utf8'));
ipcMain.handle('fs:writeFile', (_, p, c) => fs.writeFileSync(p, c, 'utf8'));
ipcMain.handle('fs:exists',    (_, p)    => fs.existsSync(p));
ipcMain.handle('fs:readDir', (_, p) => {
  const SKIP = new Set(['__pycache__', '.git', '.hg', 'node_modules', '.venv', 'venv', 'env', '.env', 'dist', 'build', '.pytest_cache']);
  return fs.readdirSync(p, { withFileTypes: true })
    .filter(e => !e.name.startsWith('.') && !SKIP.has(e.name))
    .map(e => ({
      name: e.name,
      path: path.join(p, e.name),
      isDir: e.isDirectory(),
      isPython: !e.isDirectory() && /\.(py|pyw)$/.test(e.name),
      size: e.isDirectory() ? 0 : (() => { try { return fs.statSync(path.join(p, e.name)).size; } catch { return 0; } })(),
    }))
    .sort((a, b) => a.isDir !== b.isDir ? (a.isDir ? -1 : 1) : a.name.localeCompare(b.name));
});
ipcMain.handle('fs:showInFinder', (_, p) => shell.showItemInFolder(p));
ipcMain.handle('fs:mkdirp', (_, p) => fs.mkdirSync(p, { recursive: true }));

// ── App lifecycle ────────────────────────────────────────────────

// Window title IPC
ipcMain.on('set-title', (event, title) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  if (win) win.setTitle(title || 'PyFlow IDE');
});

// Reveal in Finder/Explorer
ipcMain.on('show-in-finder', (event, filePath) => {
  const { shell } = require('electron');
  shell.showItemInFolder(filePath);
});
app.whenReady().then(async () => {
  nativeTheme.themeSource = 'dark';
  pythonPath = findPython();

  if (!pythonPath) {
    dialog.showErrorBox(
      'Python 未找到',
      [
        'PyFlow 需要 Python 3.9 或更新版本。',
        '請安裝 Python 後重新啟動：',
        'https://www.python.org/downloads/',
      ].join('\n'),
    );
    app.quit();
    return;
  }

  // Show loading splash
  const splash = new BrowserWindow({ width: 360, height: 200, frame: false, backgroundColor: '#1a1625', alwaysOnTop: true });
  splash.loadURL(`data:text/html,<style>body{margin:0;background:#1a1625;color:#c4b5fd;font-family:system-ui;display:flex;flex-direction:column;align-items:center;justify-content:center;height:200px;gap:12px}</style><div style="font-size:28px">⬡</div><div style="font-size:15px;font-weight:700">PyFlow IDE</div><div style="font-size:12px;color:#7c3aed">正在啟動…</div>`);

  try {
    await startFlask();
    await waitForPort(flaskPort);
  } catch (err) {
    splash.close();
    dialog.showErrorBox('啟動失敗', String(err));
    app.quit();
    return;
  }

  splash.close();
  buildMenu();
  createWindow();

  app.on('activate', () => { if (!mainWin) createWindow(); });
});

app.on('window-all-closed', () => {
  isQuitting = true;
  if (flask) { try { flask.kill(); } catch {} }
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  isQuitting = true;
  if (flask) { try { flask.kill(); flask = null; } catch {} }
});
