// Caption segment normalisation — shared by the AI-caption IPC result path
// (validated before captions ever reach a project) and covered by unit tests
// via scripts/build-captions-cjs.js (same pattern as zoom.cjs).

/** Round to 2 decimals without float dust. */
function round2(v) {
  return Math.round(Number(v) * 100) / 100;
}

/**
 * Validate/normalise ASR output into project captions.
 * Accepts [{ start, end, text }] (seconds, any numeric junk tolerated),
 * returns clean ascending, non-overlapping-safe segments:
 *  - drops non-finite/negative/zero-or-negative-length spans and empty text;
 *  - clamps to [0, duration] when a duration is given, dropping clamped-away
 *    spans;
 *  - sorts by start and merges overlaps (keeps the earlier text, extends its
 *    end — ASR engines must not overlap, but a bad engine must not corrupt
 *    the timeline either);
 *  - caps the list at maxSegments (pathological output guard).
 */
function normalizeCaptionSegments(raw, { duration = null, maxSegments = 4000 } = {}) {
  if (!Array.isArray(raw)) return [];
  const dur = Number.isFinite(duration) && duration > 0 ? duration : null;
  const rows = [];
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue;
    const start = Number(item.start);
    const end = Number(item.end);
    const text = typeof item.text === 'string' ? item.text.trim() : '';
    if (!text) continue;
    if (!Number.isFinite(start) || !Number.isFinite(end)) continue;
    if (start < 0 || end <= start) continue;
    const s = round2(start);
    let e = round2(end);
    if (e <= s) continue;
    if (dur !== null) {
      if (s >= dur) continue;
      e = Math.min(e, round2(dur));
      if (e <= s) continue;
    }
    rows.push({ start: s, end: e, text });
  }
  rows.sort((a, b) => a.start - b.start || a.end - b.end);
  const merged = [];
  for (const row of rows) {
    const prev = merged[merged.length - 1];
    if (prev && row.start < prev.end) {
      // Overlap: keep the earlier sentence, extend it to cover the intruder.
      prev.end = Math.max(prev.end, row.end);
      continue;
    }
    merged.push(row);
    if (merged.length >= maxSegments) break;
  }
  return merged;
}

/** Approximate on-screen character budget per caption line (CJK≈full width). */
function captionTooLong(text, maxChars = 42) {
  return text.length > maxChars;
}

module.exports = {
  round2,
  normalizeCaptionSegments,
  captionTooLong,
};
