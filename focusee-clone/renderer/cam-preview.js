'use strict';

// Round, free-floating camera preview bubble. THIS page owns the preview
// capture and runs everything in its own context — the main process only
// signals with events and never injects JS into pill pages (cross-window
// executeJavaScript is the API that natively crashed the app during
// recording teardown).

const $ = (sel) => document.querySelector(sel);
const state = { startedAt: 0, timer: null, stopped: false };
// Every camera stream this page obtains is registered here; stopPreviewTracks
// releases ALL of them. Attach signals can overlap (state replay + explicit
// attach) and each opens its own device stream — without the registry the
// superseded stream keeps the camera on after the recording stops
// (2026-11-15 user report: 停止录制后摄像头没有关).
const liveStreams = new Set();
let attachSeq = 0;

function stopPreviewTracks() {
  // Invalidate any attach still opening: when its getUserMedia resolves it
  // must release the stream instead of assigning it to a hidden page.
  attachSeq += 1;
  for (const stream of liveStreams) {
    try { stream.getTracks().forEach((t) => t.stop()); } catch {}
  }
  liveStreams.clear();
  const v = document.getElementById('cam-video');
  if (v && v.srcObject) v.srcObject = null;
  document.getElementById('bubble').classList.add('no-video');
  state.stopped = true;
}

async function attachCameraPreview() {
  const seq = attachSeq;
  const v = document.getElementById('cam-video');
  if (!v || v.srcObject) return;
  let stream = null;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false,
    });
  } catch (err) {
    // No camera / busy camera: the recording is unaffected (its capture is a
    // separate one); the bubble just stays as an empty round frame.
    console.warn('[preview] camera unavailable:', err && err.message);
    return;
  }
  // The take may have ended or the window hidden while the device was
  // opening — release immediately instead of leaking the camera.
  if (seq !== attachSeq || document.visibilityState === 'hidden' || state.stopped) {
    try { stream.getTracks().forEach((t) => t.stop()); } catch {}
    return;
  }
  stopPreviewTracks(); // release any superseded stream before adopting this one
  liveStreams.add(stream);
  v.srcObject = stream;
  document.getElementById('bubble').classList.remove('no-video');
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
  stopPreviewTracks(); // releases the previous take's streams (marks stopped)
  state.stopped = false;
  state.startedAt = startedAt;
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
