'use strict';

// Floating recording control pill (timer + stop/cancel only: the camera
// preview lives in its own round bubble window — cam-preview.*). The pill
// itself is excluded from the capture via the window's content protection
// (set in the main process).

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

// The main process REUSES this pill window across recordings: it is created
// once and re-shown for every take. A take's stop/cancel latches `stopped`
// and relabels the button ("保存中…"); when the window is reused for the next
// take, that latch must be reset or every later stop/cancel click is silently
// swallowed — the 2026-11-15 "第二次录制没有办法停止" report is exactly this.
// The pill recognises a new take by its new startedAt (per-take unique).
function rearmForNewTake(startedAt) {
  state.stopped = false;
  state.startedAt = startedAt;
  if (state.timer) clearInterval(state.timer);
  state.timer = setInterval(tick, 250);
  tick();
  $('#dot').classList.remove('paused');
  $('#btn-stop').textContent = '停止';
  $('#btn-cancel').disabled = false;
}

window.focusee.control.onState((info) => {
  if (info.startedAt && info.startedAt !== state.startedAt) {
    rearmForNewTake(info.startedAt);
  }
  $('#mic-badge').style.visibility = info.mic ? 'visible' : 'hidden';
});

// The stop flow, shared by the real button and the e2e stop signal.
function requestStop() {
  if (state.stopped) return;
  state.stopped = true;
  $('#dot').classList.add('paused');
  $('#btn-stop').textContent = '保存中…';
  window.focusee.control.stop();
}

$('#btn-stop').addEventListener('click', requestStop);

window.focusee.control.onStopSignal(requestStop);

$('#btn-cancel').addEventListener('click', () => {
  if (state.stopped) return;
  state.stopped = true;
  window.focusee.control.cancel();
});

// Tell the main process this page (and with it the focusee bridge) is alive.
// Both the recorder flow and the e2e harness key off this instead of probing
// the pill with injected JS.
try { window.focusee.control.pillReady(); } catch {}
