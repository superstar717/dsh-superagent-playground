'use strict';

// Builds the bundled demo recording (assets/sample.mp4) and the matching
// cursor track (assets/sample.cursor.json). The video is a synthetic "screen
// recording" of a dashboard so the clone has something to edit on first run;
// it is generated locally with ffmpeg and contains no third-party assets.

const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');
const ASSETS = path.join(ROOT, 'assets');
const DURATION = 6;
const W = 1280;
const H = 800;
const FPS = 30;
const FONT = '/System/Library/Fonts/Supplemental/Arial.ttf';

// Cursor keyframes: [t, x, y]. The dwells (0.9-1.6, 2.4-3.2, 4.0-4.8) are what
// the auto-zoom analyser is meant to find.
const KEYS = [
  [0.0, 420, 300],
  [0.9, 640, 180],
  [1.6, 640, 180],
  [2.4, 860, 520],
  [3.2, 860, 520],
  [4.0, 500, 560],
  [4.8, 500, 560],
  [5.4, 700, 300],
  [6.0, 760, 340],
];

function exprFor(axis) {
  // Build a nested if() over the linear segments, evaluated per frame by
  // ffmpeg. Coordinates are absolute pixels.
  const idx = axis === 'x' ? 1 : 2;
  let expr = String(KEYS[KEYS.length - 1][idx]);
  for (let i = KEYS.length - 2; i >= 0; i -= 1) {
    const [t0, , ] = KEYS[i];
    const [t1] = KEYS[i + 1];
    const v0 = KEYS[i][idx];
    const v1 = KEYS[i + 1][idx];
    const span = (t1 - t0) || 1;
    const seg = t0 === t1 ? String(v0) : `${v0}+(${v1 - v0})*(t-${t0})/${span}`;
    expr = `if(lt(t,${t1}),${seg},${expr})`;
  }
  // Commas inside an if() would be read as filter separators; escape them.
  return expr.replace(/,/g, '\\,');
}

function buildFilters() {
  const f = [];
  const box = (x, y, w, h, color = '0xffffff', t = 'fill') => `drawbox=x=${x}:y=${y}:w=${w}:h=${h}:color=${color}:t=${t}`;
  const text = (str, x, y, size, color = '0x1b1e26', weight = '') =>
    `drawtext=fontfile='${FONT}':text='${str}':x=${x}:y=${y}:fontsize=${size}:fontcolor=${color}:expansion=none${weight}`;

  f.push('drawbox=x=0:y=0:w=1280:h=800:color=0xeef1f6:t=fill');
  // top bar
  f.push(box(0, 0, W, 56));
  f.push(box(24, 18, 20, 20, '0x6c5ce7'));
  f.push(text('Dashboard', 56, 18, 20, '0x1b1e26'));
  f.push(text('Reports', 980, 20, 15, '0x6b7280'));
  f.push(text('Settings', 1080, 20, 15, '0x6b7280'));
  f.push(box(1180, 18, 72, 22, '0x6c5ce7'));
  f.push(text('Export', 1196, 21, 13, '0xffffff'));
  // sidebar
  f.push(box(0, 56, 220, 744));
  const items = ['Overview', 'Revenue', 'Customers', 'Sessions', 'Reports', 'Billing'];
  items.forEach((item, i) => {
    const y = 96 + i * 52;
    if (i === 1) f.push(box(16, y - 8, 188, 36, '0xeee9ff'));
    f.push(box(28, y + 2, 12, 12, i === 1 ? '0x6c5ce7' : '0xc7cbd6'));
    f.push(text(item, 52, y, 15, i === 1 ? '0x4b3ad6' : '0x5b6273'));
  });
  // KPI cards
  const cards = [
    [260, 90, 'Revenue', '$48,210', '+12.4%'],
    [580, 90, 'Customers', '1,284', '+3.1%'],
    [900, 90, 'Sessions', '24.8k', '+8.7%'],
  ];
  for (const [x, y, label, value, delta] of cards) {
    f.push(box(x, y, 300, 140, '0xffffff'));
    f.push(text(label, x + 22, y + 20, 15, '0x6b7280'));
    f.push(text(value, x + 22, y + 50, 32, '0x1b1e26'));
    f.push(text(delta, x + 22, y + 100, 14, '0x1fbf75'));
  }
  // chart card
  f.push(box(260, 260, 640, 440, '0xffffff'));
  f.push(text('Weekly revenue', 286, 284, 17, '0x1b1e26'));
  const bars = [180, 240, 210, 300, 260, 330, 290, 210, 280, 340, 250, 300];
  bars.forEach((h, i) => {
    const x = 300 + i * 48;
    f.push(box(x, 640 - h, 28, h, i % 3 === 0 ? '0x6c5ce7' : '0xc9c0ff'));
  });
  f.push(box(286, 660, 588, 1, '0xe4e7ef'));
  // right panel
  f.push(box(920, 260, 340, 440, '0xffffff'));
  f.push(text('Top pages', 944, 284, 17, '0x1b1e26'));
  const rows = ['/pricing', '/docs/start', '/blog/zoom', '/signup', '/changelog'];
  rows.forEach((row, i) => {
    const y = 330 + i * 58;
    f.push(box(944, y, 26, 26, '0xeef0f6'));
    f.push(text(row, 984, y + 6, 14, '0x374151'));
    f.push(box(944, y + 34, 292, 6, '0xeef0f6'));
    f.push(box(944, y + 34, 150 - i * 18, 6, '0x8b7af5'));
  });
  // cursor: white ring + dark dot
  const cx = exprFor('x');
  const cy = exprFor('y');
  f.push(`drawtext=fontfile='${FONT}':text='●':x=${cx}:y=${cy}:fontsize=26:fontcolor=0xffffff:expansion=none`);
  f.push(`drawtext=fontfile='${FONT}':text='●':x=${cx}:y=${cy}:fontsize=15:fontcolor=0x1a1a1a:expansion=none`);
  return f;
}

function generateCursorTrack() {
  const track = [];
  for (let t = 0; t <= DURATION + 1e-9; t += 0.04) {
    let i = 0;
    while (i < KEYS.length - 2 && t > KEYS[i + 1][0]) i += 1;
    const [t0, x0, y0] = KEYS[i];
    const [t1, x1, y1] = KEYS[i + 1];
    const k = t1 === t0 ? 0 : Math.min(1, Math.max(0, (t - t0) / (t1 - t0)));
    const jitter = k === 0 || k === 1 ? 1.5 : 0.4;
    track.push({
      t: Number(t.toFixed(3)),
      nx: Number(((x0 + (x1 - x0) * k + (Math.random() - 0.5) * jitter) / W).toFixed(5)),
      ny: Number(((y0 + (y1 - y0) * k + (Math.random() - 0.5) * jitter) / H).toFixed(5)),
    });
  }
  return track;
}

function run() {
  fs.mkdirSync(ASSETS, { recursive: true });
  const filters = buildFilters().join(',');
  const out = path.join(ASSETS, 'sample.mp4');
  const args = [
    '-y', '-hide_banner', '-loglevel', 'error',
    '-f', 'lavfi', '-i', `color=c=0xeef1f6:s=${W}x${H}:r=${FPS}:d=${DURATION}`,
    '-vf', filters,
    '-t', String(DURATION),
    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p',
    '-movflags', '+faststart',
    out,
  ];
  console.log('ffmpeg', args.length, 'args →', out);
  const child = spawn('ffmpeg', args, { stdio: ['ignore', 'inherit', 'inherit'] });
  child.on('close', (code) => {
    if (code !== 0) {
      console.error('ffmpeg failed with code', code);
      process.exit(code || 1);
    }
    const track = generateCursorTrack();
    fs.writeFileSync(path.join(ASSETS, 'sample.cursor.json'), JSON.stringify(track));
    const size = fs.statSync(out).size;
    console.log(`sample.mp4 ${(size / 1024).toFixed(1)} KB, cursor samples: ${track.length}`);
  });
}

run();
