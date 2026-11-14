import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const {
  buildZooms, contentRect, cursorAt, detectActions, fitRect, formatTime,
  mapPointToCanvas, normaliseCursor, sourceRectAt, zoomAt,
} = require('../renderer/zoom.cjs');

function track(points, step = 0.04) {
  // points: [[t, nx, ny], ...] piecewise linear
  const out = [];
  const end = points[points.length - 1][0];
  for (let t = 0; t <= end + 1e-9; t += step) {
    let i = 0;
    while (i < points.length - 2 && t > points[i + 1][0]) i += 1;
    const [t0, x0, y0] = points[i];
    const [t1, x1, y1] = points[i + 1];
    const k = t1 === t0 ? 0 : Math.min(1, Math.max(0, (t - t0) / (t1 - t0)));
    out.push({ t: Number(t.toFixed(3)), nx: x0 + (x1 - x0) * k, ny: y0 + (y1 - y0) * k });
  }
  return out;
}

test('detectActions finds each dwell, not the moving stretches', () => {
  const t = track([
    [0.0, 0.25, 0.25],
    [0.8, 0.25, 0.25],   // dwell 0-0.8
    [1.6, 0.7, 0.3],
    [2.4, 0.7, 0.3],     // dwell 1.6-2.4
    [3.2, 0.4, 0.7],
    [4.0, 0.4, 0.7],     // dwell 3.2-4.0
    [5.0, 0.6, 0.6],
  ]);
  const actions = detectActions(t, { radius: 0.012, minDwell: 0.45, minGap: 0.5 });
  assert.equal(actions.length, 3);
  assert.ok(Math.abs(actions[0].t - 0.4) < 0.15);
  assert.ok(Math.abs(actions[1].t - 2.0) < 0.15);
  assert.ok(Math.abs(actions[2].t - 3.6) < 0.15);
});

test('detectActions returns nothing for a cursor that never rests', () => {
  const t = track([[0, 0.1, 0.1], [4, 0.9, 0.9]]);
  assert.deepEqual(detectActions(t, { minDwell: 0.45 }), []);
});

test('buildZooms clamps to the clip and merges overlapping envelopes', () => {
  const actions = [
    { t: 0.2, nx: 0.2, ny: 0.2, dwell: 0.8 },
    { t: 0.55, nx: 0.6, ny: 0.4, dwell: 0.9 }, // envelope overlaps the first
    { t: 5.9, nx: 0.9, ny: 0.9, dwell: 0.6 },
  ];
  const zooms = buildZooms(actions, 6, { scale: 2, hold: 1, lead: 0.4, ease: 0.3, minGap: 0.4 });
  assert.equal(zooms.length, 2);
  assert.ok(zooms[0].start >= 0);
  assert.ok(zooms[zooms.length - 1].end <= 6);
  // The longer pause wins the merged focus point.
  assert.equal(zooms[0].nx, 0.6);
  assert.equal(zooms[0].scale, 2);
});

test('zoomAt: 1 outside, peak inside the hold, symmetric-ish ramps', () => {
  const zooms = [{ id: 'a', start: 1, end: 3, scale: 2, nx: 0.7, ny: 0.4, auto: true }];
  assert.equal(zoomAt(zooms, 0.5).scale, 1);
  assert.equal(zoomAt(zooms, 4).scale, 1);
  const mid = zoomAt(zooms, 2);
  assert.ok(mid.scale > 1.99, `expected the full zoom, got ${mid.scale}`);
  assert.ok(Math.abs(mid.nx - 0.7) < 0.01);
  const ramp = zoomAt(zooms, 1.15).scale;
  assert.ok(ramp > 1 && ramp < 2, `expected an intermediate scale, got ${ramp}`);
  const out = zoomAt(zooms, 2.85).scale;
  assert.ok(out > 1 && out < 2);
});

test('sourceRectAt keeps the crop inside the frame at the edges', () => {
  const r = sourceRectAt({ scale: 2, nx: 0, ny: 1 }, 1280, 800);
  assert.equal(r.sw, 640);
  assert.equal(r.sh, 400);
  assert.equal(r.sx, 0);
  assert.equal(r.sy, 400);
  // At scale 1 the whole frame is used.
  const full = sourceRectAt({ scale: 1, nx: 0.5, ny: 0.5 }, 1280, 800);
  assert.deepEqual([full.sx, full.sy, full.sw, full.sh], [0, 0, 1280, 800]);
});

test('fitRect letterboxes a 4:3 video inside a 16:9 canvas', () => {
  const r = fitRect(1600, 900, 1024, 768);
  assert.equal(r.h, 900);
  assert.equal(r.w, 1200);
  assert.equal(r.x, 200);
  assert.equal(r.y, 0);
});

test('contentRect applies padding and the chosen aspect', () => {
  const orig = contentRect(1000, 1000, 10, 'original');
  assert.equal(orig.x, 100);
  assert.equal(orig.w, 800);
  const square = contentRect(1000, 1000, 0, '1:1');
  assert.equal(square.w, 1000);
  assert.equal(square.h, 1000);
  const wide = contentRect(1000, 1000, 0, '16:9');
  assert.equal(wide.w, 1000);
  assert.equal(Math.round(wide.h), 563);
});

test('mapPointToCanvas maps the centre and hides points outside the crop', () => {
  const dest = { x: 100, y: 50, w: 800, h: 450 };
  const zoom = { scale: 1, nx: 0.5, ny: 0.5 };
  const centre = mapPointToCanvas(0.5, 0.5, zoom, dest, 1280, 720);
  assert.equal(Math.round(centre.x), 500);
  assert.equal(Math.round(centre.y), 275);
  assert.equal(centre.visible, true);
  // Zoomed in at the top-left corner: the bottom-right point is out of frame.
  const p = mapPointToCanvas(1, 1, { scale: 2, nx: 0, ny: 0 }, dest, 1280, 720);
  assert.equal(p.visible, false);
});

test('normaliseCursor converts display points to 0..1 and clamps', () => {
  const out = normaliseCursor(
    [{ t: 0, x: 0, y: 0 }, { t: 1, x: 1680, y: 1050 }, { t: 2, x: 2000, y: -20 }],
    { width: 1680, height: 1050 },
  );
  assert.deepEqual(out[0], { t: 0, nx: 0, ny: 0 });
  assert.equal(out[1].nx, 1);
  assert.equal(out[1].ny, 1);
  assert.equal(out[2].nx, 1);
  assert.equal(out[2].ny, 0);
});

test('cursorAt interpolates between samples', () => {
  const trackData = [
    { t: 0, nx: 0, ny: 0 },
    { t: 1, nx: 1, ny: 0.5 },
  ];
  const mid = cursorAt(trackData, 0.5);
  assert.equal(mid.nx, 0.5);
  assert.equal(mid.ny, 0.25);
  assert.equal(cursorAt(trackData, -1).nx, 0);
  assert.equal(cursorAt(trackData, 9).nx, 1);
});

test('formatTime renders MM:SS.cc', () => {
  assert.equal(formatTime(0), '00:00.00');
  assert.equal(formatTime(7.44), '00:07.44');
  assert.equal(formatTime(61.5), '01:01.50');
});

import { CAMERA_LAYOUTS, computeCameraRect, tiltSlices } from '../renderer/zoom.cjs';

test('computeCameraRect: corner layouts produce a circle-sized box anchored inside', () => {
  const r = computeCameraRect('bottom-right', 1280, 800, 18, 4 / 3);
  assert.equal(r.shape, 'circle');
  assert.ok(r.w > 0 && r.h > 0);
  // right edge inset by the margin (6% of the shorter side = 48)
  assert.ok(Math.abs(r.x + r.w - (1280 - 48)) <= 2, `x+w=${r.x + r.w}`);
  assert.ok(Math.abs(r.y + r.h - (800 - 48)) <= 2, `y+h=${r.y + r.h}`);
  assert.ok(r.w / r.h > 1.3 && r.w / r.h < 1.37, `aspect ${r.w / r.h}`);
});

test('computeCameraRect: bottom-center is a rounded card, horizontally centred', () => {
  const r = computeCameraRect('bottom-center', 1280, 800, 20, 4 / 3);
  assert.equal(r.shape, 'rounded');
  assert.equal(Math.abs(r.x + r.w / 2 - 640) <= 2, true);
  assert.ok(r.radius < Math.min(r.w, r.h) / 2);
});

test('computeCameraRect: size and aspect clamps hold for extreme input', () => {
  const tiny = computeCameraRect('top-left', 1280, 800, 4, 4 / 3);
  assert.ok(tiny.w >= 8);
  const tall = computeCameraRect('top-left', 1280, 800, 40, 0.5); // very tall camera
  assert.ok(tall.h <= 800 * 0.6 + 2, `h=${tall.h}`);
});

test('tiltSlices: zero tilt keeps full height, edges untouched', () => {
  const { slices } = tiltSlices({ x: 100, y: 50, w: 800, h: 400 }, 0);
  for (const sl of slices) {
    assert.ok(Math.abs(sl.dyTop - 50) < 0.01);
    assert.ok(Math.abs(sl.dyBot - 450) < 0.01);
  }
  assert.equal(slices[0].sx, 0);
});

test('tiltSlices: positive tilt shrinks the right edge like a rotate-right', () => {
  const { slices } = tiltSlices({ x: 100, y: 50, w: 800, h: 400 }, 1);
  const left = slices[0];
  const right = slices[slices.length - 1];
  assert.ok(Math.abs(left.dyTop - 50) < 0.01);
  assert.ok(right.dyTop > left.dyTop + 10, `far edge should shrink: ${right.dyTop}`);
  assert.ok(right.dyBot < left.dyBot - 10);
  // Columns tile the full width without gaps.
  assert.ok(Math.abs(slices[0].dx - 100) < 0.01);
  const last = slices[slices.length - 1];
  assert.ok(Math.abs(last.dx + last.dw - 900) < 1.5);
});

test('tiltSlices: negative tilt mirrors the direction', () => {
  const pos = tiltSlices({ x: 0, y: 0, w: 800, h: 400 }, 1).slices;
  const neg = tiltSlices({ x: 0, y: 0, w: 800, h: 400 }, -1).slices;
  // Positive tilt pivots on the left edge (right shrinks); negative mirrors:
  // the shrinking edge moves to the left.
  assert.ok(neg[0].dyTop > pos[0].dyTop + 10, `neg first top ${neg[0].dyTop}`);
  assert.ok(neg[neg.length - 1].dyTop < 1, 'neg right edge keeps full height');
});

import { activeCameraSettings } from '../renderer/zoom.cjs';

test('activeCameraSettings: defaults when no segment covers the time', () => {
  const cam = { layout: 'top-left', size: 22, segments: [{ id: 'a', start: 3, end: 5, layout: 'bottom-right', size: 30 }] };
  assert.deepEqual(activeCameraSettings(cam, 1), { layout: 'top-left', size: 22, segmentId: null });
});

test('activeCameraSettings: the last overlapping segment wins', () => {
  const cam = {
    layout: 'top-left', size: 22,
    segments: [
      { id: 'a', start: 1, end: 4, layout: 'bottom-right', size: 30 },
      { id: 'b', start: 2, end: 5, layout: 'bottom-center', size: 25 },
    ],
  };
  assert.equal(activeCameraSettings(cam, 1.5).segmentId, 'a');
  assert.equal(activeCameraSettings(cam, 3).segmentId, 'b');
  assert.equal(activeCameraSettings(cam, 3).layout, 'bottom-center');
  assert.equal(activeCameraSettings(cam, 6).segmentId, null);
});

test('activeCameraSettings: clamps sizes and tolerates malformed segments', () => {
  const cam = { layout: 'bottom-right', size: 18, segments: [null, { start: 0, end: 2, size: 999 }, { end: 3 }] };
  const r = activeCameraSettings(cam, 1);
  assert.equal(r.size, 40); // clamped
  const empty = activeCameraSettings({}, 5);
  assert.equal(empty.layout, 'bottom-right');
  assert.equal(empty.segmentId, null);
});
