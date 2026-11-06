import React, { FC, useMemo } from "react";
import {
  AbsoluteFill,
  Easing,
  Sequence,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import timingData from "./timing.json";
import { SceneVisual } from "./SceneVisuals";
import { FONT, ACCENT } from "./theme";

export type Chunk = { text: string; start: number; end: number };
export type Scene = {
  id: string;
  chip: string;
  text: string;
  audioFile: string;
  startFrame: number;
  durationFrames: number;
  chunks: Chunk[];
};
type TimingData = {
  fps: number;
  width: number;
  height: number;
  totalFrames: number;
  scenes: Scene[];
};
const T = timingData as unknown as TimingData;

const BRAND_RE_SOURCE = "(superagent|Claude\\s?Code|Cursor|GPT|豆包|甲方|质变|AI)";

export const HighlightedText: FC<{ text: string }> = ({ text }) => {
  const parts = useMemo(() => {
    const nodes: React.ReactNode[] = [];
    const re = new RegExp(BRAND_RE_SOURCE, "gi");
    let last = 0;
    let k = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(text))) {
      if (m.index > last) nodes.push(<span key={k++}>{text.slice(last, m.index)}</span>);
      nodes.push(
        <span key={k++} style={{ color: ACCENT }}>
          {m[0]}
        </span>
      );
      last = m.index + m[0].length;
    }
    if (last < text.length) nodes.push(<span key={k++}>{text.slice(last)}</span>);
    return nodes;
  }, [text]);
  return <>{parts}</>;
};

const Background: FC = () => {
  const frame = useCurrentFrame();
  const x1 = 300 + Math.sin(frame / 170) * 180;
  const y1 = 520 + Math.cos(frame / 210) * 160;
  const x2 = 760 + Math.cos(frame / 190) * 150;
  const y2 = 1380 + Math.sin(frame / 150) * 170;
  return (
    <AbsoluteFill>
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, #0b1120 0%, #0a0f1c 45%, #0c1222 100%)",
        }}
      />
      <AbsoluteFill style={{ overflow: "hidden" }}>
        <div
          style={{
            position: "absolute",
            left: x1 - 500,
            top: y1 - 500,
            width: 1000,
            height: 1000,
            borderRadius: "50%",
            background:
              "radial-gradient(circle, rgba(40,120,255,0.18) 0%, rgba(40,120,255,0.05) 45%, rgba(40,120,255,0) 70%)",
          }}
        />
        <div
          style={{
            position: "absolute",
            left: x2 - 460,
            top: y2 - 460,
            width: 920,
            height: 920,
            borderRadius: "50%",
            background:
              "radial-gradient(circle, rgba(150,80,255,0.15) 0%, rgba(150,80,255,0.04) 45%, rgba(150,80,255,0) 70%)",
          }}
        />
      </AbsoluteFill>
      <AbsoluteFill
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)",
          backgroundSize: "72px 72px",
          maskImage:
            "radial-gradient(ellipse at 50% 42%, black 30%, transparent 78%)",
          WebkitMaskImage:
            "radial-gradient(ellipse at 50% 42%, black 30%, transparent 78%)",
        }}
      />
    </AbsoluteFill>
  );
};

const Vignette: FC = () => (
  <AbsoluteFill
    style={{
      background:
        "radial-gradient(ellipse at 50% 45%, transparent 55%, rgba(0,0,0,0.42) 100%)",
      pointerEvents: "none",
    }}
  />
);

const Progress: FC<{ frame: number }> = ({ frame }) => {
  const idx = T.scenes.findIndex(
    (s) => frame >= s.startFrame && frame < s.startFrame + s.durationFrames
  );
  return (
    <div
      style={{
        position: "absolute",
        top: 104,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        gap: 10,
      }}
    >
      {T.scenes.map((s, i) => {
        const local = frame - s.startFrame;
        const frac =
          i < idx ? 1 : i === idx ? Math.min(1, Math.max(0, local / s.durationFrames)) : 0;
        return (
          <div
            key={s.id}
            style={{
              width: 38,
              height: 6,
              borderRadius: 3,
              background: "rgba(255,255,255,0.13)",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: `${frac * 100}%`,
                height: "100%",
                background: ACCENT,
                borderRadius: 3,
              }}
            />
          </div>
        );
      })}
    </div>
  );
};

const Chip: FC<{ text: string }> = ({ text }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({ frame, fps, config: { damping: 18, mass: 0.5 } });
  return (
    <div
      style={{
        position: "absolute",
        top: 168,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        opacity: pop,
        transform: `translateY(${(1 - pop) * -14}px)`,
      }}
    >
      <div
        style={{
          padding: "14px 34px",
          borderRadius: 999,
          border: "1.5px solid rgba(83,210,255,0.35)",
          background: "rgba(83,210,255,0.08)",
          color: "rgba(210,240,255,0.92)",
          fontSize: 32,
          fontWeight: 600,
          letterSpacing: 4,
        }}
      >
        {text}
      </div>
    </div>
  );
};

const Subtitles: FC<{ frame: number }> = ({ frame }) => {
  const scene = T.scenes.find(
    (s) => frame >= s.startFrame && frame < s.startFrame + s.durationFrames
  );
  if (!scene) return null;
  const chunk = scene.chunks.find((c) => frame >= c.start && frame < c.end);
  if (!chunk) return null;
  const inA = interpolate(frame, [chunk.start, chunk.start + 5], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const outA = interpolate(frame, [chunk.end - 4, chunk.end], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const rise = interpolate(frame, [chunk.start, chunk.start + 7], [18, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  return (
    <div
      style={{
        position: "absolute",
        left: 80,
        right: 80,
        bottom: 200,
        display: "flex",
        justifyContent: "center",
        opacity: Math.min(inA, outA),
        transform: `translateY(${rise}px)`,
      }}
    >
      <div
        style={{
          maxWidth: 920,
          textAlign: "center",
          fontSize: 62,
          lineHeight: 1.4,
          fontWeight: 700,
          color: "#ffffff",
          textShadow: "0 4px 26px rgba(0,0,0,0.65), 0 1px 2px rgba(0,0,0,0.5)",
        }}
      >
        <HighlightedText text={chunk.text} />
      </div>
    </div>
  );
};

export const OralVideo: FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: "#070b14", fontFamily: FONT, color: "#fff" }}>
      <Background />
      {T.scenes.map((s) => (
        <Sequence key={s.id} from={s.startFrame} durationInFrames={s.durationFrames}>
          {/* Audio is NOT played here: Remotion's bundled ffprobe/ffmpeg (compositor-darwin)
              cannot load on macOS 13. The audio track is mixed and muxed by system ffmpeg
              (scripts/make-audio.mjs + scripts/finalize.sh) using timing.json offsets. */}
          <SceneVisual sceneId={s.id} />
          {s.chip ? <Chip text={s.chip} /> : null}
        </Sequence>
      ))}
      <Vignette />
      <Progress frame={frame} />
      <Subtitles frame={frame} />
    </AbsoluteFill>
  );
};
