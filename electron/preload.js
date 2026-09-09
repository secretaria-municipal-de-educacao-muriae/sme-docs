// Exposição mínima e segura: nada de nodeIntegration no renderer.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('smedocs', {
  getApi: () => ipcRenderer.invoke('smedocs:get-api'),
  printToPdf: (args) => ipcRenderer.invoke('smedocs:print-to-pdf', args),
  onApiReady: (cb) => ipcRenderer.on('smedocs:api-ready', (_e, info) => cb(info)),
  pickDocx: () => ipcRenderer.invoke('smedocs:pick-docx'),
  analyzeDocx: (args) => ipcRenderer.invoke('smedocs:analyze-docx', args),
  generate: (args) => ipcRenderer.invoke('smedocs:generate', args),
  openPath: (args) => ipcRenderer.invoke('smedocs:open-path', args),
});
