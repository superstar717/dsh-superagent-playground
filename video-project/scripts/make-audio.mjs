import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const here = fileURLToPath(new URL(".", import.meta.url));
const timing = JSON.parse(readFileSync(here + "../src/timing.json", "utf8"));
const FPS = timing.fps;
const totalSec = timing.totalFrames / FPS;
mkdirSync(here + "../out", { recursive: true });

// System ffmpeg: Remotion's bundled compositor cannot load on macOS 13.
const FFMPEG = "/usr/local/bin/ffmpeg";

const args = [];
const filters = [];
timing.scenes.forEach((scene, i) => {
  args.push("-i", here + `../public/${scene.audioFile}`);
  const delayMs = Math.round((scene.startFrame + 5) / FPS * 1000); // +5 = audio lead frames
  filters.push(`[${i}:a]aformat=channel_layouts=mono,adelay=${delayMs}:all=1[a${i}]`);
});
const mixIn = timing.scenes.map((_, i) => `[a${i}]`).join("");
filters.push(`${mixIn}amix=inputs=${timing.scenes.length}:normalize=0,apad=whole_dur=${totalSec.toFixed(3)},aformat=sample_rates=44100:channel_layouts=stereo[aout]`);

const out = here + "../out/audio-track.m4a";
execFileSync(FFMPEG, [
  "-y", ...args,
  "-filter_complex", filters.join(";"),
  "-map", "[aout]",
  "-c:a", "aac", "-b:a", "160k",
  out,
], { stdio: "inherit" });
console.log(`[audio] mixed ${timing.scenes.length} segments -> ${out} (${totalSec.toFixed(1)}s)`);
