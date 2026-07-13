'use strict';
const { contextBridge, ipcRenderer } = require('electron');

// Expose a safe, minimal API to the renderer
contextBridge.exposeInMainWorld('electron', {
  // ── App info ──────────────────────────────────────────────────
  getPort:     ()           => ipcRenderer.invoke('get:port'),
  getConfig:   ()           => ipcRenderer.invoke('get:config'),
  setConfig:   (patch)      => ipcRenderer.invoke('set:config', patch),
  getPlatform: ()           => ipcRenderer.invoke('get:platform'),

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
});
