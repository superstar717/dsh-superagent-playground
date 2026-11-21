'use strict';

// Round, free-floating camera preview bubble. THIS page owns the preview
// capture and runs everything in its own context — the main process only
// signals with events and never injects JS into pill pages (cross-window
// executeJavaScript is the API that natively crashed the app during
// recording teardown).

const $ = (sel) => document.querySelector(sel);
const state = { startedAt: 0, timer: null, stopped: true, attached: false };

function liveTrackCount() {
  const v = document.getElementById('cam-video');
  if (!v || !v.srcObject) return 0;
  try {
    return v.srcObject.getTracks().filter((t) => t.readyState !== 'ended').length;
  } catch {
    return 0;
  }
}

// Tell the main process (and through it the e2e harness) what this page holds.
// Pushed on every attach/stop transition — polled nowhere, injected nowhere.
function reportPreviewState() {
  try {
    window.focusee.control.reportPreviewState({
      attached: state.attached,
      startedAt: state.startedAt,
      tracksLive: liveTrackCount(),
    });
  } catch {}
}

function stopPreviewTracks(endTake = true) {
  const v = document.getElementById('cam-video');
  if (v && v.srcObject) {
    v.srcObject.getTracks().forEach((t) => t.stop());
    v.srcObject = null;
  }
  document.getElementById('bubble').classList.add('no-video');
  if (state.attached || endTake) {
    state.attached = false;
    if (endTake) {
      // Take is over: forget it entirely. A stale startedAt here is what let
      // a late attach replay re-acquire the camera AFTER the take ended and
      // hold it forever (the 45-minute camera hold reported 2026-11-16).
      state.startedAt = 0;
      state.stopped = true;
    }
    reportPreviewState();
  }
}

async function attachCameraPreview() {
  // HARD GATE: capture only while a take is actually live. Without this, any
  // late 'control:attachCamera' replay (or a stray show event) re-opens the
  // camera with no recording to feed and nothing ever stops it.
  if (!state.startedAt || state.stopped) return;
  const v = document.getElementById('cam-video');
  if (!v || v.srcObject) return;
  let stream = null;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false,
    });
    // The take may have ENDED while the permission/device handshake was in
    // flight (slow camera, busy device). Attaching then would create a live
    // stream in a hidden window that nothing will ever stop — the class
    // behind the 45-minute (2026-11-16) and 12-minute (2026-11-22) camera
    // holds. Re-check the take state AFTER the await.
    if (!state.startedAt || state.stopped) {
      stream.getTracks().forEach((t) => t.stop());
      reportPreviewState();
      return;
    }
    v.srcObject = stream;
    document.getElementById('bubble').classList.remove('no-video');
    state.attached = true;
    reportPreviewState();
  } catch (err) {
    // No camera / busy camera: the recording is unaffected (its capture is a
    // separate one); the bubble just stays as an empty round frame.
    console.warn('[preview] camera unavailable:', err && err.message);
    state.attached = false;
    reportPreviewState();
  }
}

// Stop the capture when the window hides; re-attach when it shows again with
// an active take. Same contract the pill used to have for its embedded panel.
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') {
    stopPreviewTracks(false); // window hid, but only an explicit takeEnded ends the take
  } else if (state.startedAt && !state.stopped) {
    attachCameraPreview();
  }
});
window.addEventListener('pagehide', () => stopPreviewTracks(true));

// Re-arm per take: this window is REUSED across recordings. A new startedAt
// resets the stale camera take so the bubble re-attaches fresh — without this
// a second recording would keep (or lose) the previous take's preview state.
function rearmForNewTake(startedAt) {
  state.startedAt = startedAt;
  state.stopped = false;
  stopPreviewTracks(false); // drop any previous take's tracks, keep the new take armed
  attachCameraPreview();
}

window.focusee.control.onState((info) => {
  // Explicit end-of-take from the main process fires FIRST: it must win over
  // any stale startedAt replayed around the same time.
  if (info.takeEnded) {
    stopPreviewTracks(true);
    return;
  }
  if (info.startedAt && info.startedAt !== state.startedAt) {
    rearmForNewTake(info.startedAt);
  }
  if (info.pipSize) {
    document.getElementById('cam-size-label').textContent = `${info.pipSize}%`;
  }
  // Match the baked circle's screen size (WYSIWYG ±): the transparent window
  // can leak into the capture on macOS, but when the bubble circle coincides
  // exactly with the baked circle it is visually masked by it.
  if (info.previewDiameter) {
    const d = Math.min(460, Math.max(120, Math.round(info.previewDiameter)));
    const bubble = document.getElementById('bubble');
    bubble.style.width = `${d}px`;
    bubble.style.height = `${d}px`;
  }
});

window.focusee.control.onAttachCamera(attachCameraPreview);

// PiP live adjust: window position = position in the baked video, ＋/− = size.
// The editor consumes these via record:pipMoved / record:pipResize.
function reportPip() {
  try { window.focusee.control.reportPip(); } catch {}
}
window.addEventListener('resize', reportPip);
setInterval(reportPip, 400); // dragging moves the window; report periodically

$('#cam-bigger').addEventListener('click', () => {
  try { window.focusee.control.pipResize(3); } catch {}
});
$('#cam-smaller').addEventListener('click', () => {
  try { window.focusee.control.pipResize(-3); } catch {}
});

// Tell the main process this page (and with it the focusee bridge) is alive —
// the same ACK contract as the pill's pillReady().
try { window.focusee.control.previewReady(); } catch {}
