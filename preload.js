'use strict';
const { contextBridge, ipcRenderer } = require('electron');

// Expose a safe, minimal API to the renderer. The frontend historically
// looked for window.electronAPI, while older builds exposed window.electron.
// Keep both names so packaged apps and dev browser sessions behave the same.
const api = {
  // ── App info ──────────────────────────────────────────────────
  getPort:     ()           => ipcRenderer.invoke('get:port'),
  getConfig:   ()           => ipcRenderer.invoke('get:config'),
  setConfig:   (patch)      => ipcRenderer.invoke('set:config', patch),
  getPlatform: ()           => ipcRenderer.invoke('get:platform'),
  setTitle:    (title)      => ipcRenderer.invoke('window:setTitle', title),
  openExternal:(url)        => ipcRenderer.invoke('open-external', url),

  // ── Native dialogs ────────────────────────────────────────────
  openFolder:  ()           => ipcRenderer.invoke('dialog:openFolder'),
  openFile:    ()           => ipcRenderer.invoke('dialog:openFile'),
  saveDialog:  (defaultP)   => ipcRenderer.invoke('dialog:save', defaultP),
  confirm:     (msg)        => ipcRenderer.invoke('dialog:confirm', msg),

  // ── File system ───────────────────────────────────────────────
  readFile:    (p)          => ipcRenderer.invoke('fs:readFile', p),
  writeFile:   (p, content) => ipcRenderer.invoke('fs:writeFile', p, content),
  readDir:     (p)          => ipcRenderer.invoke('fs:readDir', p),
  exists:      (p)          => ipcRenderer.invoke('fs:exists', p),
  showInFinder:(p)          => ipcRenderer.invoke('fs:showInFinder', p),
  mkdirp:      (p)          => ipcRenderer.invoke('fs:mkdirp', p),

  // ── Menu events (main → renderer) ────────────────────────────
  onMenu: (cb) => {
    ipcRenderer.removeAllListeners('menu');
    ipcRenderer.on('menu', (_, cmd) => cb(cmd));
  },
  onOpenFile: (cb) => {
    ipcRenderer.removeAllListeners('open-file');
    ipcRenderer.on('open-file', (_, path) => cb(path));
  },
  onOpenFolder: (cb) => {
    ipcRenderer.removeAllListeners('open-folder');
    ipcRenderer.on('open-folder', (_, path) => cb(path));
  },
};

contextBridge.exposeInMainWorld('electron', api);
contextBridge.exposeInMainWorld('electronAPI', api);
