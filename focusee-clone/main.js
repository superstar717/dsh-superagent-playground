'use strict';

const { app, BrowserWindow, ipcMain, desktopCapturer, screen, dialog, protocol, net, shell } = require('electron');
const path = require('node:path');
const fs = require('node:fs');
const fsp = require('node:fs/promises');
const os = require('node:os');
const { spawn } = require('node:child_process');
const { pathToFileURL } = require('node:url');

// ---------------------------------------------------------------------------
// Paths
// ---------------------------------------------------------------------------

const isE2E = process.argv.includes('--e2e');
const isSmoke = process.argv.includes('--smoke');

function dataRoot() {
  if (process.env.FOCUSEE_DATA_DIR) return process.env.FOCUSEE_DATA_DIR;
  const base = isE2E || isSmoke ? os.tmpdir() : app.getPath('userData');
  return path.join(base, isE2E || isSmoke ? 'focusee-clone-e2e' : 'focusee-clone');
}

const PROJECTS_DIR = () => path.join(dataRoot(), 'projects');
const SETTINGS_FILE = () => path.join(dataRoot(), 'settings.json');

async function ensureDirs() {
  await fsp.mkdir(PROJECTS_DIR(), { recursive: true });
}

async function readSettings() {
  try {
    return JSON.parse(await fsp.readFile(SETTINGS_FILE(), 'utf8'));
  } catch {
    return {};
  }
}

async function writeSettings(patch) {
  const cur = await readSettings();
  const next = { ...cur, ...patch };
  await fsp.writeFile(SETTINGS_FILE(), JSON.stringify(next, null, 2));
  return next;
}

function projectDir(id) {
  if (!/^[a-z0-9_-]{3,64}$/i.test(id)) throw new Error(`bad project id: ${id}`);
  return path.join(PROJECTS_DIR(), id);
}

async function loadProject(id) {
  const file = path.join(projectDir(id), 'project.json');
  const raw = await fsp.readFile(file, 'utf8');
  return JSON.parse(raw);
}

async function saveProject(project) {
  project.updatedAt = Date.now();
  const dir = projectDir(project.id);
  await fsp.mkdir(dir, { recursive: true });
  await fsp.writeFile(path.join(dir, 'project.json'), JSON.stringify(project, null, 2));
  return project;
}

async function listProjects() {
  await ensureDirs();
  const entries = await fsp.readdir(PROJECTS_DIR(), { withFileTypes: true });
  const out = [];
  for (const e of entries) {
    if (!e.isDirectory()) continue;
    try {
      const p = await loadProject(e.name);
      out.push({
        id: p.id,
        name: p.name,
        createdAt: p.createdAt,
        updatedAt: p.updatedAt,
        duration: p.duration,
        videoSize: p.videoSize,
        videoFile: p.videoFile,
        hasAudio: p.hasAudio,
        thumb: p.thumb || null,
        zoomCount: (p.zooms || []).length,
      });
    } catch {
      // ignore half-written projects
    }
  }
  out.sort((a, b) => b.updatedAt - a.updatedAt);
  return out;
}

// ---------------------------------------------------------------------------
// Recording: cursor sampling (global, no special permission needed for position)
// ---------------------------------------------------------------------------

let cursorTimer = null;
let cursorSamples = [];
let cursorStartedAt = 0;

function startCursorSampling() {
  stopCursorSampling();
  cursorSamples = [];
  cursorStartedAt = Date.now();
  const sample = () => {
    const p = screen.getCursorScreenPoint();
    cursorSamples.push({ t: (Date.now() - cursorStartedAt) / 1000, x: Math.round(p.x), y: Math.round(p.y) });
  };
  sample();
  cursorTimer = setInterval(sample, 40);
}

function stopCursorSampling() {
  if (cursorTimer) clearInterval(cursorTimer);
  cursorTimer = null;
  return cursorSamples;
}

// ---------------------------------------------------------------------------
// ffmpeg
// ---------------------------------------------------------------------------

function ffmpegCandidates() {
  const list = [];
  if (process.env.FFMPEG_PATH) list.push(process.env.FFMPEG_PATH);
  list.push('/usr/local/bin/ffmpeg', '/opt/homebrew/bin/ffmpeg', '/usr/bin/ffmpeg');
  return list;
}

function findFfmpeg() {
  for (const p of ffmpegCandidates()) {
    try {
      if (fs.existsSync(p)) return p;
    } catch {}
  }
  return null;
}

function runFfmpeg(args, onLine) {
  return new Promise((resolve, reject) => {
    const bin = findFfmpeg();
    if (!bin) return reject(new Error('ffmpeg not found'));
    const child = spawn(bin, args, { stdio: ['ignore', 'pipe', 'pipe'] });
    let stderr = '';
    child.stderr.on('data', (d) => {
      const s = d.toString();
      stderr += s;
      if (onLine) for (const line of s.split('\n')) if (line.trim()) onLine(line.trim());
    });
    child.on('error', reject);
    child.on('close', (code) => {
      if (code === 0) resolve({ ok: true });
      else reject(new Error(`ffmpeg exited ${code}: ${stderr.slice(-800)}`));
    });
  });
}

// ---------------------------------------------------------------------------
// Bundled sample project
// ---------------------------------------------------------------------------

async function ensureSampleProject() {
  try {
    const dir = path.join(PROJECTS_DIR(), 'sample');
    const manifest = path.join(dir, 'project.json');
    if (fs.existsSync(manifest)) return;
    const video = path.join(__dirname, 'assets', 'sample.mp4');
    if (!fs.existsSync(video)) return;
    const cursorFile = path.join(__dirname, 'assets', 'sample.cursor.json');
    const cursor = fs.existsSync(cursorFile)
      ? JSON.parse(await fsp.readFile(cursorFile, 'utf8'))
      : [];
    await fsp.mkdir(dir, { recursive: true });
    await fsp.copyFile(video, path.join(dir, 'recording.mp4'));
    const now = Date.now();
    await saveProject({
      id: 'sample',
      name: '示例录制 · 产品演示',
      videoFile: 'recording.mp4',
      videoSize: { width: 1280, height: 800 },
      duration: 6,
      hasAudio: false,
      style: { aspect: '16:9', padding: 6, border: 0, radius: 8, shadow: 72, blur: 0, background: 'gradient-violet' },
      zooms: [],
      cursor,
      clicks: [],
      captions: [],
      cursorFx: { enabled: true, highlight: false, color: '#ffd166' },
      createdAt: now,
      updatedAt: now,
    });
  } catch (err) {
    console.warn('[sample] could not create the sample project:', err.message);
  }
}

// ---------------------------------------------------------------------------
// Windows
// ---------------------------------------------------------------------------

let mainWindow = null;
let controlWindow = null;

function createMainWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 1040,
    minHeight: 700,
    title: 'FocuSee Clone',
    titleBarStyle: 'hiddenInset',
    backgroundColor: '#eef0f5',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      spellcheck: false,
    },
  });
  win.loadFile(path.join(__dirname, 'renderer', 'index.html'));
  win.once('ready-to-show', () => {
    win.show();
    if (isE2E) runE2E(win).catch((err) => {
      console.error('[e2e] failed:', err);
      app.exit(1);
    });
  });
  win.on('closed', () => {
    mainWindow = null;
  });
  // Keep the renderer free of unhandled dialogs while the human is not around.
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url).catch(() => {});
    return { action: 'deny' };
  });
  return win;
}

function createControlWindow() {
  const win = new BrowserWindow({
    width: 320,
    height: 76,
    resizable: false,
    frame: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    hasShadow: true,
    backgroundColor: '#111318',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  win.loadFile(path.join(__dirname, 'renderer', 'control.html'));
  win.setAlwaysOnTop(true, 'screen-saver');
  win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  // The recording pill must not end up inside the recording itself.
  win.setContentProtection(true);
  const place = () => {
    const display = screen.getPrimaryDisplay().workArea;
    const [w] = win.getSize();
    win.setPosition(Math.round(display.x + display.width / 2 - w / 2), display.y + 24, false);
  };
  place();
  return win;
}

// ---------------------------------------------------------------------------
// IPC
// ---------------------------------------------------------------------------

function registerIpc() {
  ipcMain.handle('app:info', async () => ({
    version: app.getVersion(),
    electron: process.versions.electron,
    chrome: process.versions.chrome,
    dataRoot: dataRoot(),
    ffmpeg: findFfmpeg(),
    platform: process.platform,
    isE2E,
    isSmoke,
  }));

  ipcMain.handle('projects:list', async () => listProjects());

  ipcMain.handle('projects:load', async (_e, id) => loadProject(id));

  ipcMain.handle('projects:save', async (_e, project) => saveProject(project));

  ipcMain.handle('projects:delete', async (_e, id) => {
    await fsp.rm(projectDir(id), { recursive: true, force: true });
    return true;
  });

  ipcMain.handle('projects:video', async (_e, id) => {
    const p = await loadProject(id);
    const file = path.join(projectDir(id), p.videoFile);
    const data = await fsp.readFile(file);
    return { data, mime: p.videoFile.endsWith('.webm') ? 'video/webm' : 'video/mp4' };
  });

  ipcMain.handle('projects:thumb', async (_e, { id, dataUrl }) => {
    const p = await loadProject(id);
    p.thumb = dataUrl;
    await saveProject(p);
    return true;
  });

  ipcMain.handle('media:import', async (_e, { id, video, cursor }) => {
    const dir = projectDir(id);
    await fsp.mkdir(dir, { recursive: true });
    const project = { ...video, id, cursor: cursor || [], createdAt: Date.now() };
    // video.data is a Uint8Array carried over structured clone
    await fsp.writeFile(path.join(dir, project.videoFile), Buffer.from(video.data));
    delete project.data;
    return saveProject(project);
  });

  ipcMain.handle('dialog:openVideo', async () => {
    const res = await dialog.showOpenDialog(mainWindow, {
      title: 'Import a screen recording',
      properties: ['openFile'],
      filters: [{ name: 'Video', extensions: ['mp4', 'mov', 'webm', 'm4v'] }],
    });
    if (res.canceled || !res.filePaths.length) return null;
    return res.filePaths[0];
  });

  ipcMain.handle('file:readVideo', async (_e, filePath) => {
    const data = await fsp.readFile(filePath);
    const ext = path.extname(filePath).toLowerCase();
    const mime = ext === '.webm' ? 'video/webm' : 'video/mp4';
    return { data, mime, name: path.basename(filePath), size: data.length };
  });

  // Recording -------------------------------------------------------------
  ipcMain.handle('capture:sources', async () => {
    const sources = await desktopCapturer.getSources({
      types: ['screen', 'window'],
      thumbnailSize: { width: 320, height: 200 },
      fetchWindowIcons: true,
    });
    const displays = screen.getAllDisplays();
    return sources.map((s) => {
      const display = s.display_id
        ? displays.find((d) => String(d.id) === String(s.display_id)) || null
        : null;
      return {
        id: s.id,
        name: s.name,
        kind: s.id.startsWith('screen:') ? 'screen' : 'window',
        thumbnail: s.thumbnail.toDataURL(),
        appIcon: s.appIcon ? s.appIcon.toDataURL() : null,
        displayId: s.display_id || null,
        display: display ? { width: display.size.width, height: display.size.height } : null,
      };
    });
  });

  ipcMain.handle('capture:begin', async () => {
    startCursorSampling();
    const display = screen.getPrimaryDisplay();
    return {
      startedAt: Date.now(),
      display: { width: display.size.width, height: display.size.height },
    };
  });

  ipcMain.handle('capture:end', async () => stopCursorSampling());

  ipcMain.handle('capture:showControl', async (_e, info) => {
    if (!controlWindow) controlWindow = createControlWindow();
    controlWindow.webContents.send('control:state', info);
    controlWindow.showInactive();
    if (mainWindow) mainWindow.hide();
    return true;
  });

  ipcMain.handle('capture:updateControl', async (_e, info) => {
    if (controlWindow) controlWindow.webContents.send('control:state', info);
    return true;
  });

  ipcMain.on('capture:stopRequested', () => {
    if (mainWindow) mainWindow.webContents.send('record:stopRequested');
  });

  ipcMain.handle('capture:hideControl', async () => {
    if (controlWindow) {
      controlWindow.hide();
    }
    if (mainWindow) mainWindow.show();
    return true;
  });

  // Export ----------------------------------------------------------------
  ipcMain.handle('export:saveWebm', async (_e, { defaultName, data }) => {
    const res = await dialog.showSaveDialog(mainWindow, {
      title: 'Export video',
      defaultPath: path.join(app.getPath('movies'), defaultName || 'focusee-export.webm'),
      filters: [{ name: 'WebM video', extensions: ['webm'] }],
    });
    if (res.canceled || !res.filePath) return null;
    await fsp.writeFile(res.filePath, Buffer.from(data));
    return res.filePath;
  });

  ipcMain.handle('export:toMp4', async (_e, { inputPath, outputPath, onEvent }) => {
    const target = outputPath || inputPath.replace(/\.webm$/i, '.mp4');
    await runFfmpeg(
      ['-y', '-i', inputPath, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', target],
      (line) => { if (onEvent) onEvent(line); },
    );
    return target;
  });

  ipcMain.handle('export:tempFile', async (_e, { name, data }) => {
    const dir = path.join(dataRoot(), 'exports');
    await fsp.mkdir(dir, { recursive: true });
    const file = path.join(dir, `${Date.now()}-${name || 'export.webm'}`);
    await fsp.writeFile(file, Buffer.from(data));
    return file;
  });

  ipcMain.handle('export:reveal', async (_e, filePath) => {
    shell.showItemInFolder(filePath);
    return true;
  });

  ipcMain.handle('dialog:saveProjectFile', async (_e, { name, data }) => {
    const res = await dialog.showSaveDialog(mainWindow, {
      title: 'Save project',
      defaultPath: path.join(app.getPath('documents'), name || 'project.focusee.json'),
      filters: [{ name: 'FocuSee Clone project', extensions: ['json'] }],
    });
    if (res.canceled || !res.filePath) return null;
    await fsp.writeFile(res.filePath, Buffer.from(data));
    return res.filePath;
  });

  ipcMain.handle('settings:get', async () => readSettings());
  ipcMain.handle('settings:set', async (_e, patch) => writeSettings(patch));

  // E2E helpers -----------------------------------------------------------
  ipcMain.handle('e2e:shot', async (_e, name) => {
    if (!mainWindow) return null;
    const img = await mainWindow.webContents.capturePage();
    const dir = path.join(__dirname, 'artifacts');
    await fsp.mkdir(dir, { recursive: true });
    const file = path.join(dir, `${name}.png`);
    await fsp.writeFile(file, img.toPNG());
    return file;
  });
  ipcMain.handle('e2e:quit', async () => {
    setTimeout(() => app.quit(), 120);
    return true;
  });
}

// ---------------------------------------------------------------------------
// E2E scenario (deterministic, no OS screen-capture permission needed)
// ---------------------------------------------------------------------------

async function runE2E(win) {
  const wc = win.webContents;
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const shot = async (name) => {
    const img = await wc.capturePage();
    const dir = path.join(__dirname, 'artifacts');
    await fsp.mkdir(dir, { recursive: true });
    await fsp.writeFile(path.join(dir, `${name}.png`), img.toPNG());
    console.log('[e2e] shot', name);
  };
  const evalJs = (code) => wc.executeJavaScript(code, true);
  await wait(1800);
  await evalJs(`window.__focuseeTest.ready()`);
  await wait(1200);
  await shot('01-home');
  await evalJs(`window.__focuseeTest.openSample()`);
  await wait(2500);
  await shot('02-editor');
  await evalJs(`window.__focuseeTest.selectTab('background')`);
  await wait(500);
  await shot('03-background');
  await evalJs(`window.__focuseeTest.selectTab('cursor')`);
  await wait(400);
  await shot('04-cursor');
  await evalJs(`window.__focuseeTest.previewZoom(2.4)`);
  await wait(600);
  await shot('05-zoomed-canvas');
  const report = await evalJs(`window.__focuseeTest.summary()`);
  console.log('[e2e] summary', JSON.stringify(report));
  await fsp.writeFile(path.join(__dirname, 'artifacts', 'e2e-summary.json'), JSON.stringify(report, null, 2));
  // Export one short clip to prove the render pipeline works end to end.
  if (!process.argv.includes('--e2e-no-export')) {
    const result = await evalJs(`window.__focuseeTest.exportPreview()`);
    console.log('[e2e] export', JSON.stringify(result));
    await fsp.writeFile(path.join(__dirname, 'artifacts', 'export-summary.json'), JSON.stringify(result, null, 2));
    await shot('06-export-done');
  }
  await wait(300);
  app.exit(0);
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

protocol.registerSchemesAsPrivileged([
  { scheme: 'app-media', privileges: { standard: false, secure: true, supportFetchAPI: true, stream: true } },
]);

app.whenReady().then(async () => {
  await ensureDirs();
  protocol.handle('app-media', (request) => {
    try {
      const url = new URL(request.url);
      const id = url.hostname;
      const file = decodeURIComponent(url.pathname.replace(/^\//, ''));
      return net.fetch(pathToFileURL(path.join(projectDir(id), file)).toString());
    } catch (err) {
      return new Response(`bad media url: ${err.message}`, { status: 400 });
    }
  });
  registerIpc();
  await ensureSampleProject();
  mainWindow = createMainWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) mainWindow = createMainWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  stopCursorSampling();
});
