'use strict';

// Round, free-floating camera preview bubble. THIS page owns the preview
// capture and runs everything in its own context — the main process only
// signals with events and never injects JS into pill pages (cross-window
// executeJavaScript is the API that natively crashed the app during
// recording teardown).

const $ = (sel) => document.querySelector(sel);
const state = { startedAt: 0, timer: null, stopped: false };

function stopPreviewTracks() {
  const v = document.getElementById('cam-video');
  if (v && v.srcObject) {
    v.srcObject.getTracks().forEach((t) => t.stop());
    v.srcObject = null;
  }
  document.getElementById('bubble').classList.add('no-video');
}

async function attachCameraPreview() {
  const v = document.getElementById('cam-video');
  if (!v || v.srcObject) return;
  try {
    v.srcObject = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false,
    });
    document.getElementById('bubble').classList.remove('no-video');
  } catch (err) {
    // No camera / busy camera: the recording is unaffected (its capture is a
    // separate one); the bubble just stays as an empty round frame.
    console.warn('[preview] camera unavailable:', err && err.message);
  }
}

// Stop the capture when the window hides; re-attach when it shows again with
// an active take. Same contract the pill used to have for its embedded panel.
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') {
    stopPreviewTracks();
  } else if (state.startedAt && !state.stopped) {
    attachCameraPreview();
  }
});
window.addEventListener('pagehide', stopPreviewTracks);

// Re-arm per take: this window is REUSED across recordings. A new startedAt
// resets the stale camera take so the bubble re-attaches fresh — without this
// a second recording would keep (or lose) the previous take's preview state.
function rearmForNewTake(startedAt) {
  state.stopped = false;
  state.startedAt = startedAt;
  stopPreviewTracks();
  attachCameraPreview();
}

window.focusee.control.onState((info) => {
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
