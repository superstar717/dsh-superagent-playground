import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { normalizeCaptionSegments, round2, captionTooLong } = require('../renderer/captions.cjs');

test('normalizeCaptionSegments keeps clean input as-is', () => {
  const inSegs = [
    { start: 0.5, end: 2.5, text: '你好' },
    { start: 3, end: 4.2, text: '世界' },
  ];
  assert.deepEqual(normalizeCaptionSegments(inSegs), inSegs);
});

test('drops empty text, non-finite and inverted spans', () => {
  const out = normalizeCaptionSegments([
    { start: 0, end: 1, text: '   ' },
    { start: 0, end: 1, text: null },
    { start: 'x', end: 2, text: 'bad' },
    { start: 5, end: 5, text: 'zero length' },
    { start: 6, end: 4, text: 'inverted' },
    { start: 7, end: 8, text: 'keep me' },
  ]);
  assert.deepEqual(out, [{ start: 7, end: 8, text: 'keep me' }]);
});

test('clamps to duration and drops spans beyond it', () => {
  const out = normalizeCaptionSegments([
    { start: 0, end: 2, text: 'a' },
    { start: 4.5, end: 6.5, text: 'b' }, // clamped to 5.5
    { start: 9, end: 10, text: 'c' }, // entirely past duration → dropped
  ], { duration: 5.5 });
  assert.deepEqual(out, [
    { start: 0, end: 2, text: 'a' },
    { start: 4.5, end: 5.5, text: 'b' },
  ]);
});

test('sorts by start and merges overlaps into the earlier row', () => {
  const out = normalizeCaptionSegments([
    { start: 3, end: 4, text: 'later' },
    { start: 0.2, end: 3.5, text: 'first' },
  ]);
  assert.deepEqual(out, [{ start: 0.2, end: 4, text: 'first' }]);
});

test('non-array and garbage input yields []', () => {
  assert.deepEqual(normalizeCaptionSegments(null), []);
  assert.deepEqual(normalizeCaptionSegments('nope'), []);
  assert.deepEqual(normalizeCaptionSegments([1, 'x', undefined]), []);
});

test('caps pathological output at maxSegments', () => {
  const many = Array.from({ length: 500 }, (_, i) => ({ start: i * 10, end: i * 10 + 1, text: `s${i}` }));
  assert.equal(normalizeCaptionSegments(many, { maxSegments: 50 }).length, 50);
});

test('round2 removes float dust', () => {
  assert.equal(round2(0.1 + 0.2), 0.3);
  assert.equal(round2(1.005), 1);
});

test('captionTooLong flags oversized lines', () => {
  assert.equal(captionTooLong('短'), false);
  assert.equal(captionTooLong('x'.repeat(43)), true);
  assert.equal(captionTooLong('x'.repeat(42)), false);
});
