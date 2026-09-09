// SMEDocs — casca Electron (F5 do PLANO.md).
//
// Arquitetura planejada:
//   Electron (janela + Chromium)
//     ├─ spawn ──> FastAPI (PyInstaller onedir, 127.0.0.1 em porta aleatória)
//     └─ printToPDF() ──> arquivo final
//
// Estado inteiro fica no Python. O Electron é janela, upload, revisão e exportar.
// O template de referência foi gerado pelo Chromium (Skia/PDF m152), então o
// printToPDF() aqui dentro reproduz o PDF sem dependência nova (sem WeasyPrint,
// Playwright, LibreOffice ou wkhtmltopdf).

const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');
const { spawn } = require('node:child_process');
const net = require('node:net');

let mainWindow = null;
let sidecar = null;
let apiPort = 0;
let apiBaseUrl = '';

function getFreePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.listen(0, '127.0.0.1', () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
    srv.on('error', reject);
  });
}

// Em dev: `python ../smedocs.py` (CLI atual, sem API ainda — F4 vem antes da F5).
// Em prod: sidecar PyInstaller onedir servindo FastAPI em 127.0.0.1:porta.
// Troque `startSidecar` quando a F4 entregar o `POST /ingest`, `GET /jobs/:id`,
// `CRUD /bank` e `POST /render`.
function startSidecar(port) {
  const prodBin = process.resourcesPath
    ? path.join(process.resourcesPath, 'smedocs-server', 'smedocs-server.exe')
    : null;

  if (app.isPackaged && prodBin && fs.existsSync(prodBin)) {
    sidecar = spawn(prodBin, ['serve', '--port', String(port), '--host', '127.0.0.1'], {
      stdio: 'ignore',
    });
  } else {
    // Placeholder em dev: mantém o processo vivo até a API existir.
    // Quando F4 existir: spawn('python', ['../smedocs.py', 'serve', ...]).
    sidecar = null;
  }
}

async function waitForHealth(baseUrl, timeoutMs = 15000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(`${baseUrl}/health`);
      if (res.ok) return true;
    } catch {
      // sidecar ainda subindo
    }
    await new Promise((r) => setTimeout(r, 300));
  }
  return false;
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    backgroundColor: '#EAF1FD',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  await mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));

  // Entrega handshake da API para o renderer assim que pronta.
  if (apiBaseUrl) {
    mainWindow.webContents.send('smedocs:api-ready', { baseUrl: apiBaseUrl });
  }
}

// Impressão: o mesmo motor que gerou o PDF de referência.
// O renderer manda o HTML montado (Jinja2 via API) e recebe o PDF.
ipcMain.handle('smedocs:print-to-pdf', async (event, { htmlPath, pdfPath } = {}) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  if (!win) throw new Error('janela nao encontrada');

  if (htmlPath) {
    await win.loadFile(htmlPath);
  }

  const data = await win.webContents.printToPDF({
    pageSize: 'A4',
    margins: { top: 0.55, bottom: 0.55, left: 0.55, right: 0.55 },
    printBackground: true,
  });

  const out = pdfPath || (await dialog.showSaveDialog(win, {
    defaultPath: 'apostila.pdf',
    filters: [{ name: 'PDF', extensions: ['pdf'] }],
  }).then((r) => (r.canceled ? null : r.filePath)));

  if (!out) return { canceled: true };
  fs.writeFileSync(out, data);
  return { canceled: false, path: out };
});

ipcMain.handle('smedocs:get-api', async () => ({ baseUrl: apiBaseUrl, port: apiPort }));

// Ponte de teste com o CLI Python (enquanto o sidecar FastAPI da F4 não existe).
// A UI escolhe um .docx, o main chama `smedocs.py listar/gerar` como subprocesso
// e devolve o resultado para o renderer.
const REPO_ROOT = path.join(__dirname, '..');
const PY_CANDIDATES = [
  path.join(REPO_ROOT, '.venv', 'Scripts', 'python.exe'),
  path.join(REPO_ROOT, '.venv', 'bin', 'python'),
  'python',
];
const UI_OUT = path.join(os.tmpdir(), 'smedocs-ui');

function findPython() {
  for (const p of PY_CANDIDATES) {
    if (p === 'python' || fs.existsSync(p)) return p;
  }
  return 'python';
}

function runCli(args) {
  return new Promise((resolve) => {
    const child = spawn(findPython(), [path.join(REPO_ROOT, 'smedocs.py'), ...args], {
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (d) => { stdout += d; });
    child.stderr.on('data', (d) => { stderr += d; });
    child.on('close', (code) => resolve({ code, stdout, stderr }));
    child.on('error', (err) => resolve({ code: -1, stdout, stderr: String(err) }));
  });
}

ipcMain.handle('smedocs:pick-docx', async () => {
  const win = BrowserWindow.getAllWindows()[0];
  const r = await dialog.showOpenDialog(win, {
    title: 'Escolher documento Word',
    filters: [{ name: 'Word', extensions: ['docx'] }],
    properties: ['openFile'],
  });
  if (r.canceled || !r.filePaths.length) return { canceled: true };
  return { canceled: false, path: r.filePaths[0] };
});

ipcMain.handle('smedocs:analyze-docx', async (event, { docxPath } = {}) => {
  if (!docxPath) throw new Error('nenhum .docx escolhido');
  const r = await runCli(['listar', '--docx', docxPath, '--out', UI_OUT, '-f', 'json']);
  if (r.code !== 0) throw new Error(`analisar falhou (código ${r.code}): ${r.stderr.slice(-500)}`);
  return { descriptors: JSON.parse(r.stdout) };
});

ipcMain.handle('smedocs:generate', async (event, { docxPath, descritor, formato } = {}) => {
  if (!docxPath || !descritor) throw new Error('informe o .docx e o descritor');
  const r = await runCli([
    'gerar', String(descritor), '--docx', docxPath, '--out', UI_OUT,
    '-f', formato || 'pdf', '-q',
  ]);
  if (r.code !== 0) throw new Error(`gerar falhou (código ${r.code}): ${r.stderr.slice(-500)}`);
  const outputs = r.stdout.split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
  return { outputs };
});

ipcMain.handle('smedocs:open-path', async (event, { target } = {}) => {
  if (!target) throw new Error('nenhum caminho informado');
  await shell.openPath(target);
  return { ok: true };
});

app.whenReady().then(async () => {
  apiPort = await getFreePort();
  apiBaseUrl = `http://127.0.0.1:${apiPort}`;
  startSidecar(apiPort);
  // Não bloqueia a janela se a API ainda não existe (F4 pendente).
  // waitForHealth(apiBaseUrl).then(() => mainWindow?.webContents.send(...));
  await createWindow();

  app.on('activate', async () => {
    if (BrowserWindow.getAllWindows().length === 0) await createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  if (sidecar) sidecar.kill();
});
