import React from "react";
import {
  AbsoluteFill,
  continueRender,
  delayRender,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

// ---------------------------------------------------------------- fonts
const FONT = "Pretendard";
let fontsRequested = false;
export const loadFonts = () => {
  if (fontsRequested || typeof document === "undefined") return;
  fontsRequested = true;
  const handle = delayRender("fonts");
  const faces = [
    new FontFace(FONT, `url(${staticFile("fonts/Pretendard-Bold.otf")})`, { weight: "700" }),
    new FontFace(FONT, `url(${staticFile("fonts/Pretendard-Black.otf")})`, { weight: "900" }),
  ];
  Promise.all(faces.map((f) => f.load()))
    .then((loaded) => {
      loaded.forEach((f) => document.fonts.add(f));
      continueRender(handle);
    })
    .catch((e) => {
      console.error(e);
      continueRender(handle);
    });
};
export const fontFamily = `${FONT}, sans-serif`;

// ---------------------------------------------------------------- helpers
export const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

export const usePop = (delay = 0, damping = 12) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({ frame: frame - delay, fps, config: { damping, stiffness: 140, mass: 0.7 } });
};

// ---------------------------------------------------------------- captions
export type Caption = { text: string; from: number; to: number };

export const Captions: React.FC<{ captions: Caption[] }> = ({ captions }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const cur = captions.find((c, i) => {
    const end = captions[i + 1]?.from ?? c.to + 10;
    return frame >= c.from && frame < end;
  });
  if (!cur) return null;
  const s = spring({ frame: frame - cur.from, fps, config: { damping: 14, stiffness: 220 } });
  return (
    <div
      style={{
        position: "absolute",
        top: 1300,
        left: 60,
        right: 60,
        textAlign: "center",
        fontFamily,
        fontWeight: 700,
        fontSize: 66,
        lineHeight: 1.25,
        color: "#FFFFFF",
        WebkitTextStroke: "14px #15110E",
        paintOrder: "stroke fill",
        letterSpacing: -1,
        transform: `scale(${0.9 + 0.1 * s})`,
        opacity: s,
      }}
    >
      {cur.text}
    </div>
  );
};

// ---------------------------------------------------------------- scene label (top)
export const Label: React.FC<{ text: string; delay?: number; color?: string }> = ({
  text,
  delay = 4,
  color = "#FFF4E2",
}) => {
  const p = usePop(delay, 14);
  return (
    <div
      style={{
        position: "absolute",
        top: 190,
        width: "100%",
        textAlign: "center",
        fontFamily,
        fontWeight: 900,
        fontSize: 92,
        letterSpacing: -2,
        color,
        WebkitTextStroke: "16px #15110E",
        paintOrder: "stroke fill",
        transform: `translateY(${(1 - p) * -40}px) scale(${0.85 + 0.15 * p})`,
        opacity: interpolate(p, [0, 0.4], [0, 1], clamp),
      }}
    >
      {text}
    </div>
  );
};

// ---------------------------------------------------------------- overlays
export const Vignette: React.FC = () => (
  <AbsoluteFill
    style={{
      background:
        "radial-gradient(ellipse at 50% 40%, rgba(0,0,0,0) 55%, rgba(20,12,6,0.45) 100%)," +
        "linear-gradient(180deg, rgba(0,0,0,0) 60%, rgba(15,10,6,0.55) 100%)",
      pointerEvents: "none",
    }}
  />
);

/** Slow push-in camera for a whole scene. */
export const Camera: React.FC<{
  children: React.ReactNode;
  duration: number;
  from?: number;
  to?: number;
  originY?: string;
  panX?: number;
}> = ({ children, duration, from = 1, to = 1.08, originY = "50%", panX = 0 }) => {
  const frame = useCurrentFrame();
  const t = interpolate(frame, [0, duration], [0, 1], clamp);
  const scale = from + (to - from) * t;
  return (
    <AbsoluteFill
      style={{
        transform: `translateX(${panX * t}px) scale(${scale})`,
        transformOrigin: `50% ${originY}`,
      }}
    >
      {children}
    </AbsoluteFill>
  );
};
