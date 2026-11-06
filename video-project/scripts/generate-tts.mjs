import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const here = fileURLToPath(new URL(".", import.meta.url));
const cfg = JSON.parse(readFileSync(here + "scenes.json", "utf8"));
const outDir = here + "../public/audio";
mkdirSync(outDir, { recursive: true });

const EDGE_TTS = "/Users/huweixing/miniconda3/bin/edge-tts";

for (const scene of cfg.scenes) {
  const out = `${outDir}/${scene.id}.mp3`;
  console.log(`[tts] ${scene.id}: ${scene.text}`);
  execFileSync(EDGE_TTS, [
    "--voice", cfg.voice,
    "--text", scene.text,
    "--write-media", out,
  ], { stdio: "inherit" });
}
console.log("[tts] all scenes done");
