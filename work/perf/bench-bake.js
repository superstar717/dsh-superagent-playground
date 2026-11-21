// bench-bake.js — synthetic bake-loop load benchmark (NO screen capture).
// Replicates renderer/app.js drawBakedFrame's per-frame work (full-res
// drawImage + pill mirror-fill + circle-clipped PiP draw) at 30fps/15fps,
// optionally with the same captureStream+MediaRecorder(h264, 8Mbps) handoff,
// so the bake/encode split and the 30->15 frame-rate saving can be measured
// without the ScreenCaptureKit session that wedged on this machine tonight.
// usage: electron bench-bake.js --fps=30 --rec=1 [--dur=15]
const { app, BrowserWindow } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');

const arg = (name, def) => {
  const a = process.argv.find((x) => x.startsWith(`--${name}=`));
  return a ? a.split('=')[1] : def;
};
const FPS = parseInt(arg('fps', '30'), 10);
const REC = arg('rec', '1') === '1';
const DUR = parseInt(arg('dur', '15'), 10) * 1000;
const SAMPLE = path.join(__dirname, '..', '..', 'focusee-clone', 'assets', 'sample.mp4');

app.whenReady().then(async () => {
  const win = new BrowserWindow({
    width: 320, height: 200, show: false,
    webPreferences: { backgroundThrottling: false },
  });
  // A real file:// page (data: origins cannot load file:// subresources like
  // the sample video).
  const html = `<!doctype html><script>
  const FPS = ${FPS}, REC = ${REC}, DUR = ${DUR};
  const BW = 1680, BH = 1050;
  const video = document.createElement('video');
  video.src = 'file://${SAMPLE.replace(/'/g, "%27")}';
  video.muted = true; video.loop = true; video.playsInline = true;
  const bake = document.createElement('canvas');
  bake.width = BW; bake.height = BH;
  const bctx = bake.getContext('2d');
  let draws = 0, started = 0;
  const drawBakedFrame = () => {
    if (video.readyState < 2) return;
    bctx.drawImage(video, 0, 0, BW, BH);
    // pill mirror-fill, same shape as app.js
    const px = 680, py = 49, pw = 320, ph = 76;
    bctx.save();
    bctx.translate(px, py + ph);
    bctx.scale(1, -1);
    bctx.drawImage(video, px, py + ph, pw, ph, 0, 0, pw, ph);
    bctx.restore();
    // circle-clipped PiP draw, same shape as app.js
    const d = Math.round(BH * 0.18);
    const cx = Math.round(BW * 0.82), cy = Math.round(BH * 0.82);
    bctx.save();
    bctx.beginPath();
    bctx.arc(cx, cy, d / 2, 0, Math.PI * 2);
    bctx.clip();
    const cw = Math.min(video.videoWidth || 1280, video.videoHeight || 800);
    bctx.drawImage(video, (video.videoWidth - cw) / 2, (video.videoHeight - cw) / 2, cw, cw, cx - d / 2, cy - d / 2, d, d);
    bctx.restore();
    bctx.save();
    bctx.strokeStyle = 'rgba(255,255,255,0.7)';
    bctx.lineWidth = Math.max(2, d * 0.02);
    bctx.beginPath();
    bctx.arc(cx, cy, d / 2 - bctx.lineWidth / 2, 0, Math.PI * 2);
    bctx.stroke();
    bctx.restore();
    draws += 1;
  };
  video.addEventListener('playing', () => {
    if (started) return;   // 'playing' refires on every loop wrap — arm once
    let rec = null, chunks = [];
    if (REC) {
      const stream = bake.captureStream(FPS);
      rec = new MediaRecorder(stream, { mimeType: 'video/webm;codecs=h264,opus', videoBitsPerSecond: 8_000_000 });
      rec.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
      rec.start(1000);
    }
    started = Date.now();
    const timer = setInterval(drawBakedFrame, 1000 / FPS);
    drawBakedFrame();
    setTimeout(() => {
      clearInterval(timer);
      const done = (blob) => {
        console.log('BENCH_RESULT draws=' + draws + ' fps_cfg=' + FPS + ' rec=' + REC +
          ' bytes=' + (blob ? blob.size : 0) + ' wall=' + (Date.now() - started));
        window.close();
      };
      if (rec) {
        rec.onstop = () => done(new Blob(chunks));
        rec.stop();
      } else done(null);
    }, DUR);
  });
  video.play();
  </script>`;
  const htmlPath = path.join(os.tmpdir(), `focusee-bench-bake-${FPS}-${REC}.html`);
  fs.writeFileSync(htmlPath, html);
  win.webContents.on('console-message', (_e, _l, msg) => {
    if (/^BENCH_RESULT/.test(msg)) { console.log(msg); setTimeout(() => app.exit(0), 300); }
  });
  await win.loadFile(htmlPath);
  const t = setTimeout(() => { console.log('BENCH_TIMEOUT'); app.exit(1); }, DUR + 30000);
  app.on('window-all-closed', () => { clearTimeout(t); app.exit(0); });
});
