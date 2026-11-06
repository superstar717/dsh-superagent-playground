import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const here = fileURLToPath(new URL(".", import.meta.url));
const cfg = JSON.parse(readFileSync(here + "scenes.json", "utf8"));
const FPS = cfg.fps || 30;
const LEAD_FRAMES = 5;        // silence before speech inside a scene
const TAIL_FRAMES = 17;       // breathing room after speech
const LAST_EXTRA = 66;        // end hold on final scene

function audioDuration(path) {
  const out = execFileSync("ffprobe", [
    "-v", "error", "-show_entries", "format=duration",
    "-of", "default=noprint_wrappers=1:nokey=1", path,
  ]).toString().trim();
  return parseFloat(out);
}

function charWeight(ch) {
  if (/[\u4e00-\u9fff]/.test(ch)) return 1;
  if (/[a-zA-Z0-9]/.test(ch)) return 0.32;
  if (ch === " ") return 0.3;
  return 0.5;
}

// Split scene text into display chunks (<= ~14 weight units) at punctuation.
function splitChunks(text) {
  const parts = text
    .split(/(?<=[，。：；？！、])/)
    .map((p) => p.replace(/[，。：；？！、]/g, "").trim())
    .filter(Boolean);
  const chunks = [];
  let buf = "";
  let bufW = 0;
  const weight = (s) => [...s].reduce((acc, c) => acc + charWeight(c), 0);
  for (const part of parts) {
    const w = weight(part) + (buf ? 0.3 : 0); // joiner space
    if (buf && bufW + w > 14) {
      chunks.push(buf);
      buf = part;
      bufW = w;
    } else {
      buf = buf ? buf + " " + part : part;
      bufW += w;
    }
  }
  if (buf) chunks.push(buf);
  return chunks;
}

let cursor = 0;
const scenes = cfg.scenes.map((scene) => {
  const audioFile = `audio/${scene.id}.mp3`;
  const dur = audioDuration(here + "../public/" + audioFile);
  const audioFrames = Math.round(dur * FPS);
  const isLast = scene.id === cfg.scenes[cfg.scenes.length - 1].id;
  const durationFrames = LEAD_FRAMES + audioFrames + TAIL_FRAMES + (isLast ? LAST_EXTRA : 0);

  const chunks = splitChunks(scene.text);
  const totalW = chunks.reduce((acc, c) => acc + [...c].reduce((a, ch) => a + charWeight(ch), 0), 0);
  let f = cursor + LEAD_FRAMES;
  const timedChunks = chunks.map((text) => {
    const w = [...text].reduce((a, ch) => a + charWeight(ch), 0);
    const len = Math.max(4, Math.round((w / totalW) * audioFrames));
    const chunk = { text, start: f, end: f + len };
    f += len;
    return chunk;
  });
  // fix rounding drift: last chunk ends where audio ends
  timedChunks[timedChunks.length - 1].end = cursor + LEAD_FRAMES + audioFrames;

  const def = {
    id: scene.id,
    chip: scene.chip,
    text: scene.text,
    audioFile,
    startFrame: cursor,
    durationFrames,
    chunks: timedChunks,
  };
  cursor += durationFrames;
  return def;
});

const timing = { fps: FPS, width: 1080, height: 1920, totalFrames: cursor, scenes };
writeFileSync(here + "../src/timing.json", JSON.stringify(timing, null, 2));

const totalSec = (cursor / FPS).toFixed(1);
console.log(`[timing] ${scenes.length} scenes, total ${cursor} frames = ${totalSec}s`);
for (const s of scenes) {
  console.log(`  ${s.id}: frame ${s.startFrame}–${s.startFrame + s.durationFrames} (${(s.durationFrames / FPS).toFixed(1)}s), ${s.chunks.length} chunks`);
}
