import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

// Textual tripwires for the stop-recording crash class. These pin the
// invariants that the 2026-11-15 "stop kills the app" incident broke; the
// behavioural gate is the real-machine recording e2e (--e2e-rec), not this.

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(here, '..');
const read = (p) => readFileSync(path.join(root, p), 'utf8');
const appJs = read('renderer/app.js');
const mainJs = read('main.js');
const controlJs = read('renderer/control.js');
const preloadJs = read('preload.js');

test('renderer teardown never references main-process-only identifiers', () => {
  // `mainWindow` exists only in the main process. A renderer reference throws
  // ReferenceError inside finishRecording's try AND catch, so the editor was
  // never re-shown and the save never ran: stopping a recording made the
  // whole app vanish (commit f616f88 regression).
  assert.doesNotMatch(appJs, /\bmainWindow\b/);
});

test('recorder event handlers capture the local recording state', () => {
  // finishRecording nulls S.recording before the recorders flush; handlers
  // that read back through S.recording hit null and chunks are lost.
  assert.match(appJs, /camRec\.ondataavailable = \(e\) => \{ if \(e\.data\.size\) rec\.camChunks\.push\(e\.data\); \}/);
  assert.doesNotMatch(appJs, /ondataavailable = \(e\) => \{[^}]*S\.recording\./);
});

test('onstop only signals the flush; the save is driven by finishRecording', () => {
  // saveRecordingFrom(recorder) saved the wrong object (rec.recorder was
  // undefined inside it) and crashed before writing anything.
  assert.match(appJs, /recorder\.onstop = \(\) => \{ try \{ rec\.flushDone\(\); \} catch \{\} \};/);
  assert.doesNotMatch(appJs, /onstop = \(\) => saveRecordingFrom\(/);
  assert.match(appJs, /saveRecordingFrom\(rec\)\.catch\(/);
});

test('main process never injects JS into the pill page', () => {
  // executeJavaScript into the pill during teardown natively crashed the app
  // (Electron-2026-11-15-040339.ips, SIGSEGV under the inspector bridge);
  // pill flows are event-driven now.
  assert.doesNotMatch(mainJs, /stopPillCameraPreview/);
  assert.doesNotMatch(mainJs, /controlWindow\.webContents\.executeJavaScript/);
  assert.doesNotMatch(mainJs, /win\.webContents\.executeJavaScript/);
});

test('pill camera preview and stop run in the pill context via events', () => {
  assert.match(preloadJs, /pillReady: \(\) => ipcRenderer\.send\('control:pillReady'\)/);
  assert.match(preloadJs, /onAttachCamera/);
  assert.match(preloadJs, /onStopSignal/);
  assert.match(controlJs, /onAttachCamera\(attachCameraPreview\)/);
  assert.match(controlJs, /onStopSignal\(requestStop\)/);
  assert.match(controlJs, /control\.pillReady\(\)/);
  assert.match(mainJs, /control:pillReady/);
  assert.match(mainJs, /control:attachCamera/);
  assert.match(mainJs, /control:stopSignal/);
});

test('hold mode exists so the recording e2e can leave the app running', () => {
  assert.match(mainJs, /--e2e-rec-hold/);
});
