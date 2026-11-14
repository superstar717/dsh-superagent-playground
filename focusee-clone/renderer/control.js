'use strict';

// Floating recording control pill. The pill itself is excluded from the
// capture via the window's content protection (set in the main process).

const $ = (sel) => document.querySelector(sel);
const state = { startedAt: 0, timer: null, stopped: false };

function fmt(sec) {
  const s = Math.max(0, Math.floor(sec));
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}

function tick() {
  if (!state.startedAt) return;
  $('#time').textContent = fmt((Date.now() - state.startedAt) / 1000);
}

// Stop the preview capture when the window hides — the tracks belong to THIS
// page, so stopping them here is safe (never do it via cross-window JS).
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') stopPreviewTracks();
});
window.addEventListener('pagehide', stopPreviewTracks);

function stopPreviewTracks() {
  const v = document.getElementById('cam-video');
  if (v && v.srcObject) {
    v.srcObject.getTracks().forEach((t) => t.stop());
    v.srcObject = null;
  }
}

// Camera preview attach — ALWAYS in this page's own context. The main process
// merely signals; cross-window executeJavaScript into this page is forbidden
// (it natively crashed the app when used during recording teardown).
async function attachCameraPreview() {
  const v = document.getElementById('cam-video');
  if (!v || v.srcObject) return;
  try {
    v.srcObject = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 640 } }, audio: false });
  } catch (err) {
    // No camera / busy camera: recording itself is unaffected (its capture is
    // separate); just leave the preview off.
    console.warn('[control] camera preview unavailable:', err.message);
  }
}
window.focusee.control.onAttachCamera(attachCameraPreview);

window.focusee.control.onState((info) => {
  if (info.startedAt && !state.startedAt) {
    state.startedAt = info.startedAt;
    state.timer = setInterval(tick, 250);
    tick();
  }
  $('#mic-badge').style.visibility = info.mic ? 'visible' : 'hidden';
  if (info.withCamera) {
    document.getElementById('cam-panel').classList.remove('hidden');
    document.getElementById('cam-size-label').textContent = `${info.pipSize}%`;
    // The attach signal can arrive before this page finishes loading and
    // registers its listener — re-drive the attach from the state itself.
    attachCameraPreview();
  }
});

// PiP live adjust: window position = position in the baked video, +/− = size.
function reportPip() {
  try { window.focusee.control.reportPip(); } catch {}
}
document.getElementById('cam-bigger').addEventListener('click', () => {
  try { window.focusee.control.pipResize(3); } catch {}
});
document.getElementById('cam-smaller').addEventListener('click', () => {
  try { window.focusee.control.pipResize(-3); } catch {}
});
window.addEventListener('resize', reportPip);
setInterval(reportPip, 400); // drag moves the window; report position periodically

// The stop flow, shared by the real button and the e2e stop signal.
function requestStop() {
  if (state.stopped) return;
  state.stopped = true;
  $('#dot').classList.add('paused');
  $('#btn-stop').textContent = '保存中…';
  stopPreviewTracks(); // own-context, safe
  window.focusee.control.stop();
}

$('#btn-stop').addEventListener('click', requestStop);

window.focusee.control.onStopSignal(requestStop);

$('#btn-cancel').addEventListener('click', () => {
  if (state.stopped) return;
  state.stopped = true;
  stopPreviewTracks();
  window.focusee.control.cancel();
});

// Tell the main process this page (and with it the focusee bridge) is alive.
// Both the recorder flow and the e2e harness key off this instead of probing
// the pill with injected JS.
try { window.focusee.control.pillReady(); } catch {}
