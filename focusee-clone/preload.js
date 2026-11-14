'use strict';

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('focusee', {
  info: () => ipcRenderer.invoke('app:info'),

  projects: {
    list: () => ipcRenderer.invoke('projects:list'),
    load: (id) => ipcRenderer.invoke('projects:load', id),
    save: (project) => ipcRenderer.invoke('projects:save', project),
    remove: (id) => ipcRenderer.invoke('projects:delete', id),
    video: (id) => ipcRenderer.invoke('projects:video', id),
    thumb: (id, dataUrl) => ipcRenderer.invoke('projects:thumb', { id, dataUrl }),
    importVideo: (payload) => ipcRenderer.invoke('media:import', payload),
    openVideoDialog: () => ipcRenderer.invoke('dialog:openVideo'),
    readVideoFile: (filePath) => ipcRenderer.invoke('file:readVideo', filePath),
  },

  capture: {
    sources: () => ipcRenderer.invoke('capture:sources'),
    begin: () => ipcRenderer.invoke('capture:begin'),
    end: () => ipcRenderer.invoke('capture:end'),
    showControl: (info) => ipcRenderer.invoke('capture:showControl', info),
    updateControl: (info) => ipcRenderer.invoke('capture:updateControl', info),
    hideControl: () => ipcRenderer.invoke('capture:hideControl'),
    stop: () => ipcRenderer.send('capture:stopRequested'),
    onStopRequested: (cb) => {
      const handler = () => cb();
      ipcRenderer.on('record:stopRequested', handler);
      return () => ipcRenderer.removeListener('record:stopRequested', handler);
    },
  },

  control: {
    onState: (cb) => {
      const handler = (_e, info) => cb(info);
      ipcRenderer.on('control:state', handler);
      return () => ipcRenderer.removeListener('control:state', handler);
    },
    stop: () => ipcRenderer.send('capture:stopRequested'),
  },

  exporter: {
    saveWebm: (defaultName, data) => ipcRenderer.invoke('export:saveWebm', { defaultName, data }),
    tempFile: (name, data) => ipcRenderer.invoke('export:tempFile', { name, data }),
    toMp4: (inputPath, outputPath) => ipcRenderer.invoke('export:toMp4', { inputPath, outputPath }),
    reveal: (filePath) => ipcRenderer.invoke('export:reveal', filePath),
    saveProjectFile: (name, data) => ipcRenderer.invoke('dialog:saveProjectFile', { name, data }),
  },

  settings: {
    get: () => ipcRenderer.invoke('settings:get'),
    set: (patch) => ipcRenderer.invoke('settings:set', patch),
  },

  e2e: {
    shot: (name) => ipcRenderer.invoke('e2e:shot', name),
    quit: () => ipcRenderer.invoke('e2e:quit'),
  },
});
