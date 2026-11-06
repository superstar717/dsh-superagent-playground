import React, { FC } from "react";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { FONT, ACCENT, VIOLET, WARM } from "./theme";

const card: React.CSSProperties = {
  background: "rgba(255,255,255,0.045)",
  border: "1.5px solid rgba(255,255,255,0.10)",
  borderRadius: 32,
  boxShadow: "0 24px 80px rgba(0,0,0,0.45)",
};

const gradientText: React.CSSProperties = {
  backgroundImage: `linear-gradient(92deg, ${ACCENT}, ${VIOLET})`,
  WebkitBackgroundClip: "text",
  backgroundClip: "text",
  color: "transparent",
};

const usePop = (delay = 0, damping = 15, mass = 0.7) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({ frame: frame - delay, fps, config: { damping, mass } });
};

const Stage: FC<{ children: React.ReactNode }> = ({ children }) => (
  <AbsoluteFill
    style={{
      alignItems: "center",
      justifyContent: "center",
      fontFamily: FONT,
      position: "absolute",
      top: 60,
    }}
  >
    {children}
  </AbsoluteFill>
);

const Rings: FC<{ color?: string }> = ({ color = ACCENT }) => {
  const frame = useCurrentFrame();
  const phase = (frame % 90) / 90;
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      {[0, 45].map((off) => {
        const p = ((frame + off) % 90) / 90;
        return (
          <div
            key={off}
            style={{
              position: "absolute",
              width: 300 + p * 900,
              height: 300 + p * 900,
              borderRadius: "50%",
              border: `2px solid ${color}`,
              opacity: 0.35 * (1 - p),
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};

/* ---------------- s1: hook ---------------- */
const Scene1: FC = () => {
  const p1 = usePop(6, 13);
  const p2 = usePop(34, 11, 0.9);
  const p3 = usePop(60, 16);
  return (
    <Stage>
      <Rings />
      <div style={{ textAlign: "center" }}>
        <div
          style={{
            fontSize: 92,
            fontWeight: 700,
            letterSpacing: 10,
            opacity: p1,
            transform: `translateY(${(1 - p1) * 30}px)`,
          }}
        >
          工作方式
        </div>
        <div
          style={{
            fontSize: 260,
            fontWeight: 800,
            letterSpacing: 16,
            marginTop: 40,
            ...gradientText,
            opacity: p2,
            transform: `scale(${0.7 + p2 * 0.3})`,
            filter: `drop-shadow(0 0 60px rgba(83,210,255,${0.5 * p2}))`,
          }}
        >
          质变
        </div>
        <div
          style={{
            marginTop: 56,
            fontSize: 40,
            color: "rgba(255,255,255,0.55)",
            letterSpacing: 6,
            opacity: p3,
          }}
        >
          发生了什么？
        </div>
      </div>
    </Stage>
  );
};

/* ---------------- s2: chat era ---------------- */
const Scene2: FC = () => {
  const pCard = usePop(4, 17);
  const pUser = usePop(16, 15);
  const pAi = usePop(46, 15);
  const frame = useCurrentFrame();
  const showPaste = interpolate(frame, [150, 170], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const dotPhase = Math.floor(frame / 14) % 3;
  return (
    <Stage>
      <div style={{ width: 880, transform: `translateY(${(1 - pCard) * 40}px)`, opacity: pCard }}>
        <div style={{ ...card, padding: 36 }}>
          <div style={{ display: "flex", gap: 10, marginBottom: 30 }}>
            {["#ff5f57", "#febc2e", "#28c840"].map((c) => (
              <div key={c} style={{ width: 18, height: 18, borderRadius: 9, background: c, opacity: 0.8 }} />
            ))}
            <div style={{ marginLeft: 12, color: "rgba(255,255,255,0.5)", fontSize: 30 }}>
              AI 助手 · 一问一答
            </div>
          </div>
          <div style={{ display: "flex", justifyContent: "flex-start", opacity: pUser, transform: `translateX(${(1 - pUser) * -30}px)` }}>
            <div
              style={{
                background: "rgba(83,210,255,0.16)",
                border: "1.5px solid rgba(83,210,255,0.35)",
                borderRadius: "26px 26px 26px 6px",
                padding: "24px 34px",
                fontSize: 40,
                fontWeight: 600,
              }}
            >
              帮我出个方案
            </div>
          </div>
          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 28, opacity: pAi, transform: `translateX(${(1 - pAi) * 30}px)` }}>
            <div
              style={{
                background: "rgba(255,255,255,0.07)",
                border: "1.5px solid rgba(255,255,255,0.12)",
                borderRadius: "26px 26px 6px 26px",
                padding: "24px 34px",
                fontSize: 40,
              }}
            >
              {frame < 60 ? (
                <span style={{ display: "inline-flex", gap: 10 }}>
                  {[0, 1, 2].map((i) => (
                    <span
                      key={i}
                      style={{
                        width: 14,
                        height: 14,
                        borderRadius: 7,
                        background: "rgba(255,255,255,0.7)",
                        opacity: dotPhase === i ? 1 : 0.3,
                        display: "inline-block",
                      }}
                    />
                  ))}
                </span>
              ) : (
                "好的，方案如下…"
              )}
            </div>
          </div>
        </div>
        <div
          style={{
            marginTop: 36,
            display: "flex",
            justifyContent: "center",
            opacity: showPaste,
            transform: `translateY(${(1 - showPaste) * 24}px)`,
          }}
        >
          <div
            style={{
              padding: "18px 40px",
              borderRadius: 999,
              border: `1.5px solid rgba(255,122,107,0.5)`,
              background: "rgba(255,122,107,0.12)",
              color: WARM,
              fontSize: 38,
              fontWeight: 700,
              letterSpacing: 2,
            }}
          >
            ⧉ 复制 · 粘贴 · 自己动手
          </div>
        </div>
      </div>
    </Stage>
  );
};

/* ---------------- s3: coding agents ---------------- */
const TERMINAL_LINES = [
  { text: "$ claude", color: "rgba(255,255,255,0.9)", dur: 12 },
  { text: "> 修复这个 bug，并跑通测试", color: ACCENT, dur: 26 },
  { text: "✓ 已定位问题", color: "#5eead4", dur: 14 },
  { text: "✓ 已完成修改", color: "#5eead4", dur: 14 },
  { text: "✓ 测试全部通过", color: "#5eead4", dur: 14 },
];
const Scene3: FC = () => {
  const p = usePop(4, 17);
  const frame = useCurrentFrame();
  let cursorTime = 24;
  return (
    <Stage>
      <div style={{ width: 900, opacity: p, transform: `translateY(${(1 - p) * 40}px)` }}>
        <div style={{ ...card, padding: 0, overflow: "hidden" }}>
          <div style={{ display: "flex", gap: 10, padding: "26px 32px", background: "rgba(255,255,255,0.04)" }}>
            {["#ff5f57", "#febc2e", "#28c840"].map((c) => (
              <div key={c} style={{ width: 20, height: 20, borderRadius: 10, background: c, opacity: 0.8 }} />
            ))}
            <div style={{ marginLeft: 12, color: "rgba(255,255,255,0.45)", fontSize: 30 }}>
              终端 · AI 自己动手
            </div>
          </div>
          <div style={{ padding: "40px 44px", fontSize: 40, lineHeight: 1.85, fontFamily: '"SF Mono", Menlo, monospace' }}>
            {TERMINAL_LINES.map((line, li) => {
              const start = cursorTime;
              cursorTime += line.dur + 8;
              const visible = Math.max(
                0,
                Math.floor(
                  interpolate(frame, [start, start + line.dur], [0, line.text.length], {
                    extrapolateLeft: "clamp",
                    extrapolateRight: "clamp",
                  })
                )
              );
              const isLast = li === TERMINAL_LINES.length - 1;
              const showCursor = visible > 0 && visible < line.text.length;
              return (
                <div key={li} style={{ color: line.color, whiteSpace: "pre-wrap" }}>
                  {line.text.slice(0, visible)}
                  {showCursor ? <span style={{ opacity: Math.floor(frame / 8) % 2 ? 1 : 0.2 }}>▌</span> : null}
                  {isLast && visible >= line.text.length ? (
                    <span style={{ opacity: Math.floor(frame / 8) % 2 ? 1 : 0.2 }}>▌</span>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </Stage>
  );
};

/* ---------------- s4: endless ping-pong ---------------- */
const Scene4: FC = () => {
  const p = usePop(4, 16);
  const frame = useCurrentFrame();
  const cycle = Math.floor(frame / 36) % 3;
  const labels = ["提出想法", "反复确认", "来回修改"];
  const bounce = Math.sin(frame / 7) * 16;
  return (
    <Stage>
      <div style={{ opacity: p, alignItems: "center", display: "flex", flexDirection: "column", position: "relative" }}>
        <div
          style={{
            width: 240,
            height: 240,
            borderRadius: "50%",
            border: "2px solid rgba(255,255,255,0.25)",
            background: "rgba(255,255,255,0.06)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 84,
            fontWeight: 800,
          }}
        >
          人
        </div>
        <div style={{ position: "relative", height: 300, width: 700, marginTop: 8, marginBottom: 8 }}>
          {[0, 1].map((i) => (
            <div
              key={i}
              style={{
                position: "absolute",
                left: i === 0 ? 150 : 470,
                top: 30 + (i === 0 ? bounce : -bounce) + 60,
                fontSize: 56,
                color: WARM,
                opacity: 0.9,
              }}
            >
              {i === 0 ? "↑" : "↓"}
            </div>
          ))}
          {labels.map((l, i) => (
            <div
              key={l}
              style={{
                position: "absolute",
                left: 190 + i * 110,
                top: 118,
                padding: "12px 26px",
                borderRadius: 999,
                fontSize: 34,
                fontWeight: 700,
                border: `1.5px solid ${cycle === i ? "rgba(255,122,107,0.7)" : "rgba(255,255,255,0.12)"}`,
                background: cycle === i ? "rgba(255,122,107,0.18)" : "rgba(255,255,255,0.05)",
                color: cycle === i ? WARM : "rgba(255,255,255,0.45)",
                transition: "none",
              }}
            >
              {l}
            </div>
          ))}
          <div
            style={{
              position: "absolute",
              right: 0,
              top: 60,
              fontSize: 64,
              fontWeight: 800,
              color: WARM,
              opacity: 0.75 + 0.25 * Math.sin(frame / 9),
            }}
          >
            ×N
          </div>
        </div>
        <div
          style={{
            width: 240,
            height: 240,
            borderRadius: "50%",
            border: "2px solid rgba(255,122,107,0.5)",
            background: "rgba(255,122,107,0.10)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 84,
            fontWeight: 800,
            color: WARM,
          }}
        >
          AI
        </div>
      </div>
    </Stage>
  );
};

/* ---------------- s5: requirement card + superagent ---------------- */
const Scene5: FC = () => {
  const pCard = usePop(4, 15);
  const pStamp = usePop(95, 12, 0.9);
  const pLogo = usePop(50, 15);
  const frame = useCurrentFrame();
  const glow = 0.4 + 0.25 * Math.sin(frame / 10);
  return (
    <Stage>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
        <div style={{ ...card, width: 860, padding: 44, position: "relative", opacity: pCard, transform: `translateY(${(1 - pCard) * 50}px)` }}>
          <div style={{ fontSize: 34, color: "rgba(255,255,255,0.5)", letterSpacing: 6 }}>需求单</div>
          <div style={{ fontSize: 60, fontWeight: 800, marginTop: 26, lineHeight: 1.4 }}>
            需求，说清楚<span style={{ color: ACCENT }}>就行</span>
          </div>
          <div style={{ fontSize: 36, color: "rgba(255,255,255,0.55)", marginTop: 22 }}>
            目标 · 上下文 · 验收标准
          </div>
          <div
            style={{
              position: "absolute",
              right: 40,
              top: 36,
              padding: "14px 30px",
              border: `4px solid rgba(255,122,107,0.85)`,
              borderRadius: 18,
              color: "rgba(255,122,107,0.95)",
              fontSize: 46,
              fontWeight: 800,
              letterSpacing: 10,
              transform: "rotate(-12deg)",
              opacity: pStamp,
            }}
          >
            甲方
          </div>
        </div>
        <div
          style={{
            marginTop: 90,
            fontSize: 96,
            fontWeight: 800,
            letterSpacing: 2,
            ...gradientText,
            opacity: pLogo,
            transform: `scale(${0.75 + pLogo * 0.25})`,
            filter: `drop-shadow(0 0 50px rgba(167,139,250,${glow * pLogo}))`,
          }}
        >
          superagent
        </div>
        <div
          style={{
            marginTop: 26,
            padding: "14px 44px",
            borderRadius: 999,
            border: "1.5px solid rgba(83,210,255,0.4)",
            background: "rgba(83,210,255,0.10)",
            color: "rgba(215,242,255,0.95)",
            fontSize: 36,
            fontWeight: 600,
            letterSpacing: 8,
            opacity: pLogo,
          }}
        >
          接管执行
        </div>
      </div>
    </Stage>
  );
};

/* ---------------- s6: autonomous checklist ---------------- */
const ROWS = [
  { label: "拆解需求", delay: 14 },
  { label: "执行任务", delay: 45 },
  { label: "自主验证", delay: 75 },
  { label: "交付结果", delay: 125 },
];
const Scene6: FC = () => {
  const p = usePop(4, 17);
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const doneCount = ROWS.filter((r) => frame >= r.delay + 10).length;
  return (
    <Stage>
      <div style={{ width: 860, opacity: p, transform: `translateY(${(1 - p) * 40}px)` }}>
        <div style={{ ...card, padding: 0, overflow: "hidden" }}>
          <div style={{ height: 14, background: "rgba(255,255,255,0.08)" }}>
            <div
              style={{
                height: "100%",
                width: `${(doneCount / ROWS.length) * 100}%`,
                background: `linear-gradient(90deg, ${ACCENT}, ${VIOLET})`,
              }}
            />
          </div>
          <div style={{ padding: "44px 48px" }}>
            <div style={{ fontSize: 32, color: "rgba(255,255,255,0.5)", letterSpacing: 4, marginBottom: 34 }}>
              superagent · 自动推进
            </div>
            {ROWS.map((r, i) => {
              const ok = frame >= r.delay + 10;
              const pop = spring({ frame: frame - r.delay, fps, config: { damping: 12, mass: 0.5 } });
              return (
                <div
                  key={r.label}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 28,
                    padding: "26px 0",
                    borderBottom: i < ROWS.length - 1 ? "1px solid rgba(255,255,255,0.07)" : "none",
                    opacity: ok ? 1 : 0.45,
                  }}
                >
                  <div
                    style={{
                      width: 64,
                      height: 64,
                      borderRadius: 18,
                      border: ok ? `2px solid rgba(94,234,212,0.8)` : "2px solid rgba(255,255,255,0.2)",
                      background: ok ? "rgba(94,234,212,0.12)" : "transparent",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 40,
                      color: "#5eead4",
                      fontWeight: 800,
                    }}
                  >
                    <span style={{ opacity: pop, display: "inline-block", transform: `scale(${pop})` }}>✓</span>
                  </div>
                  <div style={{ fontSize: 46, fontWeight: 700 }}>{r.label}</div>
                  {ok && i === ROWS.length - 1 ? (
                    <div style={{ marginLeft: "auto", color: "#5eead4", fontSize: 36, fontWeight: 700 }}>
                      已交付
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </Stage>
  );
};

/* ---------------- s7: before / after ---------------- */
const Scene7: FC = () => {
  const pTop = usePop(4, 16);
  const pArrow = usePop(30, 14);
  const pBottom = usePop(46, 15);
  const frame = useCurrentFrame();
  const arrowY = Math.sin(frame / 9) * 10;
  return (
    <Stage>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: 900 }}>
        <div
          style={{
            ...card,
            width: "100%",
            padding: "40px 48px",
            opacity: pTop * 0.85,
            filter: "saturate(0.4) brightness(0.8)",
          }}
        >
          <div style={{ fontSize: 32, color: "rgba(255,255,255,0.45)", letterSpacing: 4 }}>以前</div>
          <div style={{ fontSize: 54, fontWeight: 700, marginTop: 20, color: "rgba(255,255,255,0.75)" }}>
            人 ⇄ AI 工具，不停地沟通
          </div>
          <div style={{ marginTop: 18, display: "flex", gap: 12 }}>
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                style={{
                  width: 14,
                  height: 14,
                  borderRadius: 7,
                  background: "rgba(255,255,255,0.6)",
                  opacity: Math.floor(frame / 10) % 3 === i ? 1 : 0.25,
                  display: "inline-block",
                }}
              />
            ))}
          </div>
        </div>
        <div style={{ margin: "26px 0", fontSize: 64, color: ACCENT, opacity: pArrow, transform: `translateY(${arrowY}px)` }}>
          ▼
        </div>
        <div
          style={{
            ...card,
            width: "100%",
            padding: "44px 48px",
            borderColor: "rgba(83,210,255,0.55)",
            background: "rgba(83,210,255,0.09)",
            boxShadow: "0 24px 90px rgba(30,120,220,0.35)",
            opacity: pBottom,
            transform: `translateY(${(1 - pBottom) * 40}px)`,
          }}
        >
          <div style={{ fontSize: 32, color: "rgba(215,242,255,0.7)", letterSpacing: 4 }}>现在</div>
          <div style={{ fontSize: 60, fontWeight: 800, marginTop: 20 }}>
            提需求 <span style={{ color: ACCENT }}>→</span> 等交付
          </div>
          <div style={{ marginTop: 18, fontSize: 36, color: "rgba(255,255,255,0.6)" }}>
            像甲方一样，就够了
          </div>
        </div>
      </div>
    </Stage>
  );
};

/* ---------------- s8: ending ---------------- */
const Scene8: FC = () => {
  const p1 = usePop(6, 15);
  const p2 = usePop(40, 11, 0.9);
  const p3 = usePop(72, 15);
  const frame = useCurrentFrame();
  const glow = 0.35 + 0.25 * Math.sin(frame / 10);
  return (
    <Stage>
      <Rings color={VIOLET} />
      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: 64, fontWeight: 600, color: "rgba(255,255,255,0.72)", letterSpacing: 6, opacity: p1 }}>
          这不是一次工具升级
        </div>
        <div
          style={{
            fontSize: 150,
            fontWeight: 800,
            letterSpacing: 10,
            marginTop: 48,
            lineHeight: 1.3,
            ...gradientText,
            opacity: p2,
            transform: `scale(${0.72 + p2 * 0.28})`,
            filter: `drop-shadow(0 0 70px rgba(167,139,250,${glow * p2}))`,
          }}
        >
          是工作方式的
          <br />
          质变
        </div>
        <div
          style={{
            marginTop: 70,
            fontSize: 52,
            fontWeight: 700,
            color: ACCENT,
            letterSpacing: 3,
            opacity: p3,
          }}
        >
          superagent
        </div>
      </div>
    </Stage>
  );
};

const MAP: Record<string, FC> = {
  s1: Scene1,
  s2: Scene2,
  s3: Scene3,
  s4: Scene4,
  s5: Scene5,
  s6: Scene6,
  s7: Scene7,
  s8: Scene8,
};

export const SceneVisual: FC<{ sceneId: string }> = ({ sceneId }) => {
  const C = MAP[sceneId];
  if (!C) return null;
  return <C />;
};
