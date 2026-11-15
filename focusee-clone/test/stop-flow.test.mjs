import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

// Textual tripwires for the recording-stop and preview-window classes of bug.
// These pin the invariants behind the 2026-11-15 incidents: "stop kills the
// app" (6bc7e837b928) and "second recording can't be stopped + camera preview
// embedded in the square pill" (865c48b0088f). The behavioural gate is the
// real-machine recording e2e (--e2e-rec / --e2e-rec-two), not this.

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(here, '..');
const read = (p) => readFileSync(path.join(root, p), 'utf8');
const appJs = read('renderer/app.js');
const mainJs = read('main.js');
const controlJs = read('renderer/control.js');
const controlHtml = read('renderer/control.html');
const camPreviewJs = read('renderer/cam-preview.js');
const camPreviewHtml = read('renderer/cam-preview.html');
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

test('main process never injects JS into the pill/preview pages', () => {
  // executeJavaScript into the pill during teardown natively crashed the app
  // (Electron-2026-11-15-040339.ips, SIGSEGV under the inspector bridge);
  // pill flows are event-driven now.
  assert.doesNotMatch(mainJs, /stopPillCameraPreview/);
  assert.doesNotMatch(mainJs, /controlWindow\.webContents\.executeJavaScript/);
  assert.doesNotMatch(mainJs, /previewWindow\.webContents\.executeJavaScript/);
  assert.doesNotMatch(mainJs, /win\.webContents\.executeJavaScript/);
});

test('pill re-arms for a new take — the reused window must not latch stop', () => {
  // The pill window is REUSED across recordings. A take's stop/cancel latches
  // `stopped`; without a reset on the next take's new startedAt, every later
  // stop/cancel click is silently swallowed — the "second recording can't be
  // stopped" report (865c48b0088f).
  assert.match(controlJs, /function rearmForNewTake\(/);
  assert.match(controlJs, /state\.stopped = false/);
  assert.match(controlJs, /info\.startedAt !== state\.startedAt/);
  assert.match(controlJs, /rearmForNewTake\(info\.startedAt\)/);
  assert.match(controlJs, /onStopSignal\(requestStop\)/);
});

test('camera preview lives in its own round bubble, not inside the pill', () => {
  // The preview used to be embedded as a rectangle in the square control pill
  // while the baked PiP is a circle; the bubble window is also the surface
  // whose position drives the baked PiP (归属与裁剪, 865c48b0088f).
  assert.match(mainJs, /function createCameraPreviewWindow\(/);
  assert.match(mainJs, /transparent: true/);
  assert.match(camPreviewHtml, /border-radius: 50%/);
  assert.match(camPreviewHtml, /overflow: hidden/);
  assert.doesNotMatch(controlHtml, /cam-panel/);
  assert.doesNotMatch(controlJs, /attachCameraPreview/);
  // The pill must never grow to host a preview again.
  assert.doesNotMatch(mainJs, /Math\.max\(h, 380\)/);
});

test('pill and bubble run their media in their own context via events', () => {
  assert.match(preloadJs, /pillReady: \(\) => ipcRenderer\.send\('control:pillReady'\)/);
  assert.match(preloadJs, /previewReady: \(\) => ipcRenderer\.send\('control:previewReady'\)/);
  assert.match(preloadJs, /onAttachCamera/);
  assert.match(preloadJs, /onStopSignal/);
  assert.match(camPreviewJs, /onAttachCamera\(attachCameraPreview\)/);
  assert.match(camPreviewJs, /control\.previewReady\(\)/);
  assert.match(controlJs, /control\.pillReady\(\)/);
  assert.match(mainJs, /control:pillReady/);
  assert.match(mainJs, /control:previewReady/);
  assert.match(mainJs, /control:attachCamera/);
  assert.match(mainJs, /control:stopSignal/);
});

test('bubble and pill are excluded from the recording capture', () => {
  // Both windows carry setContentProtection(true) — a preview that leaks into
  // its own recording is exactly the failure mode this must prevent.
  const protections = mainJs.match(/setContentProtection\(true\)/g) || [];
  assert.ok(protections.length >= 2, `expected ≥2 content-protected windows, got ${protections.length}`);
});

test('e2e harness can reproduce the two-take path and leave the app running', () => {
  assert.match(mainJs, /--e2e-rec-two/);
  assert.match(mainJs, /--e2e-rec-takes=/);
  assert.match(mainJs, /--e2e-rec-cancel-take=/);
  assert.match(mainJs, /--e2e-rec-hold/);
  assert.match(mainJs, /runRecordingTake/);
  // e2e launches must not fight the installed app for the same userData lock.
  assert.match(mainJs, /--focusee-user-data/);
});

test('cancel path is event-driven and resets with the same latch', () => {
  // The cancel button shares the stopped latch with stop; the harness drives
  // it through the page's own handler (no JS injection into pill pages).
  assert.match(controlJs, /function requestCancel\(/);
  assert.match(controlJs, /onCancelSignal\(requestCancel\)/);
  assert.match(preloadJs, /onCancelSignal/);
  assert.match(mainJs, /control:cancelSignal/);
});

test('stop-signal replay reaches pages that loaded after showControl', () => {
  // First-take flakiness class: state sent before the page finished loading
  // was lost; did-finish-load replays the latest per-take info.
  assert.match(mainJs, /did-finish-load/);
  assert.match(mainJs, /replayControlInfo/);
});

test('preview position math never double-unwraps the display bounds', () => {
  // 2026-11-15 crash (user dragged the bubble): `const display =
  // getPrimaryDisplay().bounds` followed by `display.bounds.x` read `.bounds`
  // off the bounds object — undefined — and threw an uncaught exception in
  // the main process. Every display lookup now keeps the Display object and
  // unwraps .bounds exactly once, with a guard.
  assert.doesNotMatch(mainJs, /getPrimaryDisplay\(\)\.bounds;[\s\S]{0,200}\.bounds\./);
  const reportMove = mainJs.match(/const reportMove = \(\) => \{[\s\S]{0,600}?\n  \};/);
  assert.ok(reportMove, 'preview reportMove block not found');
  assert.match(reportMove[0], /const display = screen\.getPrimaryDisplay\(\);/);
  assert.match(reportMove[0], /if \(!display\) return;/);
  // Unwrap exactly once into a fresh name; never read .bounds off the bounds.
  assert.match(reportMove[0], /const b = display\.bounds;/);
  assert.match(reportMove[0], /- b\.x\)/);
  assert.doesNotMatch(reportMove[0], /display\.bounds\./);
  // The harness must exercise a real bubble move so this class ships broken
  // never again.
  assert.match(mainJs, /bubble-move-updates-pip/);
  assert.match(appJs, /pipLive: \(\) =>/);
});
