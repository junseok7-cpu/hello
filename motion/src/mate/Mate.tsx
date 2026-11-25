import React from "react";
import {
  AbsoluteFill,
  Audio,
  Img,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import timing from "./timing.json";
import taps from "./taps.json";
import companies from "./companies.json";
import { clamp, fontFamily, loadFonts } from "../common/ui";

loadFonts();

type Scene = (typeof timing.scenes)[number];
type SceneProps = { scene: Scene; dur: number };

// brand colors sampled from the MATE site
const BLUE = "#2563EB";
const NAVY = "#17233B";
const BG = "#EDF1F7";
const SKY = "#EAF0FB";
const MUTED = "#64748B";

const cap = (scene: Scene, i: number) => scene.captions[Math.min(i, scene.captions.length - 1)].from;
const shot = (n: string) => staticFile(`mate/screens/${n}.png`);

const useSpring = (delay = 0, damping = 13, stiffness = 160) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({ frame: f - delay, fps, config: { damping, stiffness, mass: 0.7 } });
};

const COMPANIES = [
  ["BNK", "BNK시스템", "금융 IT"],
  ["KD", "경동도시가스", "에너지"],
  ["N", "넥센타이어", "모빌리티"],
  ["MH", "무학", "식음료"],
  ["BX", "바이넥스", "바이오"],
  ["PNC", "부산신항만", "물류"],
  ["SW", "성우하이텍", "미래차"],
  ["SJ", "세정", "패션"],
  ["K", "케이조선", "조선"],
  ["HZ", "하이즈항공", "항공우주"],
] as const;

// ================================================================ shared pieces
const Caption: React.FC<{ scene: Scene; hide?: number[] }> = ({ scene, hide = [] }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const caps = scene.captions;
  const i = caps.findIndex((c, k) => f >= c.from && f < (caps[k + 1]?.from ?? 99999));
  if (i < 0 || hide.includes(i)) return null;
  const c = caps[i];
  const s = spring({ frame: f - c.from, fps, config: { damping: 15, stiffness: 240 } });
  return (
    <div style={{ position: "absolute", top: 1468, width: "100%", display: "flex", justifyContent: "center" }}>
      <div
        style={{
          fontFamily,
          fontWeight: 900,
          fontSize: 62,
          letterSpacing: -1.5,
          color: NAVY,
          background: "#FFFFFF",
          padding: "18px 38px",
          borderRadius: 28,
          boxShadow: "0 14px 40px rgba(23,35,59,0.18)",
          transform: `translateY(${(1 - s) * 24}px) scale(${0.92 + 0.08 * s})`,
          opacity: s,
          maxWidth: 960,
          textAlign: "center",
        }}
      >
        {c.text}
      </div>
    </div>
  );
};

const Label: React.FC<{ text: string; delay?: number }> = ({ text, delay = 2 }) => {
  const p = useSpring(delay, 14);
  return (
    <div style={{ position: "absolute", top: 150, width: "100%", display: "flex", justifyContent: "center" }}>
      <div
        style={{
          fontFamily,
          fontWeight: 900,
          fontSize: 54,
          letterSpacing: -1,
          color: "#fff",
          background: BLUE,
          padding: "14px 36px",
          borderRadius: 999,
          transform: `translateY(${(1 - p) * -30}px) scale(${0.8 + 0.2 * p})`,
          opacity: p,
          boxShadow: "0 12px 30px rgba(37,99,235,0.35)",
        }}
      >
        {text}
      </div>
    </div>
  );
};

const Backdrop: React.FC<{ color?: string }> = ({ color = BG }) => (
  <AbsoluteFill style={{ background: color }}>
    <AbsoluteFill
      style={{
        backgroundImage:
          "linear-gradient(rgba(37,99,235,0.06) 2px, transparent 2px), linear-gradient(90deg, rgba(37,99,235,0.06) 2px, transparent 2px)",
        backgroundSize: "90px 90px",
      }}
    />
  </AbsoluteFill>
);

const Logo: React.FC<{ size?: number; dot?: number }> = ({ size = 200, dot = 1 }) => (
  <div style={{ display: "flex", alignItems: "flex-end", fontFamily, fontWeight: 900, fontSize: size, letterSpacing: -size * 0.04, color: NAVY, lineHeight: 1 }}>
    MATE
    <div
      style={{
        width: size * 0.2,
        height: size * 0.2,
        borderRadius: "50%",
        background: BLUE,
        marginLeft: size * 0.06,
        marginBottom: size * 0.1,
        transform: `scale(${dot})`,
      }}
    />
  </div>
);

/** company badge in the site's style */
const Badge: React.FC<{ code: string; size?: number }> = ({ code, size = 84 }) => (
  <div
    style={{
      width: size,
      height: size,
      borderRadius: size * 0.28,
      background: SKY,
      color: BLUE,
      fontFamily,
      fontWeight: 900,
      fontSize: size * (code.length > 2 ? 0.3 : 0.4),
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      flexShrink: 0,
    }}
  >
    {code}
  </div>
);

const Tile: React.FC<{ c: readonly [string, string, string]; w?: number; style?: React.CSSProperties }> = ({ c, w = 440, style }) => (
  <div
    style={{
      width: w,
      background: "#fff",
      borderRadius: 30,
      padding: "22px 26px",
      display: "flex",
      alignItems: "center",
      gap: 22,
      boxShadow: "0 12px 34px rgba(23,35,59,0.13)",
      fontFamily,
      ...style,
    }}
  >
    <Badge code={c[0]} />
    <div>
      <div style={{ fontWeight: 900, fontSize: 40, color: NAVY, letterSpacing: -1 }}>{c[1]}</div>
      <div style={{ fontWeight: 700, fontSize: 28, color: MUTED }}>{c[2]}</div>
    </div>
  </div>
);


// ---------------------------------------------------------------- mountain of company names (from the team's list)
const chipW = (n: string) => 34 + [...n].reduce((w, ch) => w + (/[가-힣]/.test(ch) ? 28 : ch === " " ? 8 : /[A-Z&]/.test(ch) ? 19 : 16), 0);
const PICKED: string[] = companies.picked;
const CELL_W = 236;
const CELL_GAP = 9;
const PILE = (() => {
  // tidy grid: 4 columns, 가나다 order, equal-size boxes
  const names = [...companies.all].sort((a, b) => a.localeCompare(b, "ko"));
  const cols = 4;
  const left = (1080 - cols * CELL_W - (cols - 1) * CELL_GAP) / 2;
  return names.map((n, i) => ({
    n,
    x: left + (i % cols) * (CELL_W + CELL_GAP),
    y: 400 + Math.floor(i / cols) * 58,
    w: CELL_W,
    fs: Math.min(27, (27 * (CELL_W - 22)) / (chipW(n) - 34)),
    i,
  }));
})();

/** grid slot centers of the 10-company tiles (Research scene) */
const gridCenter = (i: number) => [i % 2 ? 785 : 295, 364 + Math.floor(i / 2) * 222];

const Mountain: React.FC<{ start: number; per: number; highlight?: number; gather?: number; wobble?: number }> = ({
  start,
  per,
  highlight = 0,
  gather = 0,
  wobble = 0,
}) => {
  const f = useCurrentFrame();
  return (
    <>
      {PILE.map((c, i) => {
        const s = spring({ frame: f - start - i * per, fps: 30, config: { damping: 14, stiffness: 170, mass: 0.6 } });
        if (s < 0.001) return null;
        const pi = PICKED.indexOf(c.n);
        const picked = pi >= 0;
        const h = picked ? highlight : 0;
        let x = c.x;
        let y = c.y + (1 - s) * 30;
        if (picked && gather > 0) {
          const [gx, gy] = gridCenter(pi);
          x = x + (gx - c.w / 2 - x) * gather;
          y = y + (gy - 22 - y) * gather;
        }
        const wob = wobble * Math.sin(f / 4 + i * 1.7) * 10;
        return (
          <div
            key={c.n}
            style={{
              position: "absolute",
              left: x + wob,
              top: y,
              width: c.w,
              height: 48,
              borderRadius: 12,
              background: h > 0.5 ? BLUE : "#fff",
              border: `3px solid ${h > 0.5 ? BLUE : "#CBD5E1"}`,
              color: h > 0.5 ? "#fff" : NAVY,
              fontFamily,
              fontWeight: 900,
              fontSize: c.fs,
              letterSpacing: -0.5,
              whiteSpace: "nowrap",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: h > 0.5 ? "0 12px 30px rgba(37,99,235,0.45)" : "0 6px 14px rgba(23,35,59,0.12)",
              opacity: Math.min(1, s) * (picked ? 1 : 1 - 0.85 * highlight),
              transform: `scale(${1 + 0.22 * h * (1 - gather)}) rotate(${wob * 0.4}deg)`,
              zIndex: picked ? 2 : 1,
            }}
          >
            {c.n}
          </div>
        );
      })}
    </>
  );
};


// ---------------------------------------------------------------- opening: a messy heap of names (1.5x chips)
const rnd = (i: number, k: number) => {
  const x = Math.sin(i * 127.1 + k * 311.7) * 43758.5453;
  return x - Math.floor(x);
};
const HEAP_H = 66;
const HEAP = (() => {
  // drop each chip at a random x; it lands on whatever is already there (height map), slightly sinking in
  const hm = new Array(140).fill(1990); // 10px columns, x from -100 to 1300
  return companies.all.map((n, i) => {
    const w = chipW(n) * 1.5;
    const cx = 540 + (rnd(i, 1) + rnd(i, 2) + rnd(i, 3) - 1.5) * 800;
    const x = Math.max(-80, Math.min(1160 - w, cx - w / 2));
    const a = Math.floor((x + 100) / 10);
    const b = Math.ceil((x + w + 100) / 10);
    let top = Infinity;
    for (let k = a; k < b; k++) top = Math.min(top, hm[k]);
    const y = top - HEAP_H + 16 * (0.6 + 0.8 * rnd(i, 4));
    for (let k = a; k < b; k++) hm[k] = Math.min(hm[k], y + HEAP_H * 0.25);
    return { n, x, y, w, rot: ((i * 47) % 36) - 18, spin: rnd(i, 5) > 0.5 ? 1 : -1 };
  });
})();

const Heap: React.FC<{ start: number; per: number; wobble?: number }> = ({ start, per, wobble = 0 }) => {
  const f = useCurrentFrame();
  return (
    <>
      {HEAP.map((c, i) => {
        const s = spring({ frame: f - start - i * per, fps: 30, config: { damping: 9, stiffness: 200, mass: 0.6 } });
        if (s < 0.001) return null;
        const wob = wobble * Math.sin(f / 4 + i * 1.7) * 8;
        return (
          <div
            key={c.n}
            style={{
              position: "absolute",
              left: c.x + wob,
              top: c.y - (1 - s) * 1700,
              width: c.w,
              height: HEAP_H,
              borderRadius: 18,
              background: "#fff",
              border: "4px solid #94A3B8",
              color: NAVY,
              fontFamily,
              fontWeight: 900,
              fontSize: 40,
              letterSpacing: -0.5,
              whiteSpace: "nowrap",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 8px 18px rgba(23,35,59,0.22)",
              transform: `rotate(${c.rot + (1 - s) * 70 * c.spin + wob * 0.5}deg)`,
            }}
          >
            {c.n}
          </div>
        );
      })}
    </>
  );
};

// ---------------------------------------------------------------- phone with real screenshots
const SHOT_W = 860; // screenshots are 430px @2x
const SHOT_H = 1864;

const Phone: React.FC<{
  src: string;
  width?: number;
  scroll?: number; // in screenshot px
  x?: number;
  y?: number;
  scale?: number;
  rotate?: number;
  children?: React.ReactNode; // overlays in screenshot px space
  tall?: boolean;
}> = ({ src, width = 520, scroll = 0, x = 540, y = 270, scale = 1, rotate = 0, children, tall }) => {
  const k = width / SHOT_W;
  const h = SHOT_H * k;
  const bezel = 16;
  return (
    <div
      style={{
        position: "absolute",
        left: x - width / 2 - bezel,
        top: y,
        width: width + bezel * 2,
        height: h + bezel * 2,
        borderRadius: 78,
        background: NAVY,
        boxShadow: "0 40px 90px rgba(23,35,59,0.35)",
        transform: `scale(${scale}) rotate(${rotate}deg)`,
        transformOrigin: "50% 50%",
      }}
    >
      <div style={{ position: "absolute", left: bezel, top: bezel, width, height: h, borderRadius: 62, overflow: "hidden", background: "#fff" }}>
        <div style={{ position: "absolute", left: 0, top: -scroll * k, width: SHOT_W, transform: `scale(${k})`, transformOrigin: "0 0" }}>
          <Img src={src} style={{ width: SHOT_W, display: "block", height: tall ? undefined : SHOT_H }} />
          {children}
        </div>
      </div>
      <div style={{ position: "absolute", left: "50%", top: bezel + 14, width: 150, height: 40, marginLeft: -75, borderRadius: 20, background: NAVY }} />
    </div>
  );
};

/** tap ripple at a screenshot coordinate, starting at frame `at` */
const Tap: React.FC<{ x: number; y: number; at: number }> = ({ x, y, at }) => {
  const f = useCurrentFrame() - at;
  if (f < -4 || f > 18) return null;
  const press = interpolate(f, [-4, 0, 4], [0, 1, 1], clamp);
  const r = interpolate(f, [0, 16], [30, 110], clamp);
  const o = interpolate(f, [0, 16], [0.55, 0], clamp);
  return (
    <>
      <div style={{ position: "absolute", left: x - r, top: y - r, width: r * 2, height: r * 2, borderRadius: "50%", border: `8px solid ${BLUE}`, opacity: o }} />
      <div
        style={{
          position: "absolute",
          left: x - 38,
          top: y - 38,
          width: 76,
          height: 76,
          borderRadius: "50%",
          background: "rgba(23,35,59,0.35)",
          border: "5px solid rgba(255,255,255,0.9)",
          opacity: press * interpolate(f, [10, 18], [1, 0], clamp),
          transform: `scale(${1.2 - 0.2 * press})`,
        }}
      />
    </>
  );
};

const Chip: React.FC<{ text: string; icon: React.ReactNode; at: number; x: number; y: number; from?: number }> = ({ text, icon, at, x, y, from = -1 }) => {
  const p = useSpring(at, 11, 180);
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        display: "flex",
        alignItems: "center",
        gap: 16,
        background: "#fff",
        borderRadius: 999,
        padding: "18px 32px 18px 22px",
        fontFamily,
        fontWeight: 900,
        fontSize: 46,
        color: NAVY,
        boxShadow: "0 16px 40px rgba(23,35,59,0.22)",
        opacity: interpolate(p, [0, 0.3], [0, 1], clamp),
        transform: `translateX(${(1 - p) * 200 * from}px) scale(${0.7 + 0.3 * p}) rotate(${(1 - p) * 8 * from}deg)`,
      }}
    >
      <div style={{ width: 64, height: 64, borderRadius: "50%", background: BLUE, display: "flex", alignItems: "center", justifyContent: "center" }}>{icon}</div>
      {text}
    </div>
  );
};

const LockIcon = () => (
  <svg width={36} height={36} viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth={2.6} strokeLinecap="round">
    <rect x="5" y="11" width="14" height="10" rx="2" />
    <path d="M8 11V7a4 4 0 0 1 7.5-2" />
  </svg>
);
const ClockIcon = () => (
  <svg width={36} height={36} viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth={2.6} strokeLinecap="round">
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </svg>
);
const SearchIcon: React.FC<{ size?: number; color?: string }> = ({ size = 52, color = BLUE }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2.8} strokeLinecap="round">
    <circle cx="11" cy="11" r="7" />
    <path d="M20 20l-4-4" />
  </svg>
);

// ================================================================ 1. hook
const RESEARCH_NOTES = ["매출액", "직원 리뷰", "복지 제도", "채용 공고", "근무지", "연봉", "성장성", "ESG"];

const Hook: React.FC<SceneProps> = ({ scene, dur }) => {
  const f = useCurrentFrame();
  const c1 = cap(scene, 1);
  const c2 = cap(scene, 2);
  const c3 = cap(scene, 3);
  const c4 = cap(scene, 4);
  const query = "나에게 맞는 회사";
  const typed = query.slice(0, Math.floor(interpolate(f, [6, 36], [0, query.length], clamp)));
  const barUp = spring({ frame: f - c1 + 4, fps: 30, config: { damping: 16 } });
  const chaos = interpolate(f, [c3, c4], [0, 1], clamp);
  const dark = interpolate(f, [c4 - 4, c4 + 10], [0, 1], clamp);
  const zoom = interpolate(f, [c3, dur], [1, 1.12], clamp);
  const tabs = Math.floor(interpolate(f, [c2, c3 + 20], [3, 63], clamp));
  return (
    <AbsoluteFill>
      <Backdrop />
      <AbsoluteFill style={{ transform: `scale(${zoom}) rotate(${chaos * -2}deg)` }}>
        {/* search bar */}
        <div
          style={{
            position: "absolute",
            left: 90,
            width: 900,
            top: interpolate(barUp, [0, 1], [760, 250]),
            height: 150,
            borderRadius: 999,
            background: "#fff",
            boxShadow: "0 20px 50px rgba(23,35,59,0.16)",
            display: "flex",
            alignItems: "center",
            gap: 26,
            padding: "0 50px",
            fontFamily,
            fontWeight: 900,
            fontSize: 62,
            color: NAVY,
            transform: `scale(${1 - barUp * 0.12})`,
          }}
        >
          <SearchIcon size={64} />
          {typed}
          <div style={{ width: 6, height: 70, background: BLUE, opacity: Math.floor(f / 8) % 2 ? 1 : 0.15 }} />
        </div>
        {/* tab counter */}
        {f >= c2 && (
          <div
            style={{
              position: "absolute",
              right: 100,
              top: 170,
              background: "#EF4444",
              color: "#fff",
              fontFamily,
              fontWeight: 900,
              fontSize: 40,
              padding: "10px 26px",
              borderRadius: 999,
              transform: `scale(${1 + 0.15 * Math.sin(f / 2)})`,
            }}
          >
            열린 탭 {tabs}개
          </div>
        )}
        {/* company names piling up from the bottom like a heap of trash */}
        <Heap start={c1 - 2} per={(c3 - c1 - 6) / HEAP.length} wobble={chaos} />
        {/* research notes piling up */}
        {RESEARCH_NOTES.map((n, i) => {
          const d = c2 + i * 3.5;
          const s = spring({ frame: f - d, fps: 30, config: { damping: 12, stiffness: 150 } });
          const tx = i % 2 ? 730 + ((i * 37) % 70) : 40 + ((i * 53) % 60);
          const ty = 470 + Math.floor(i / 2) * 120 + ((i * 29) % 30);
          const rot = ((i * 71) % 30) - 15;
          const wob = chaos * Math.cos(f / 3.5 + i * 2) * 18;
          return (
            <div
              key={n}
              style={{
                position: "absolute",
                left: tx + wob,
                top: ty,
                padding: "20px 30px",
                background: i % 3 === 0 ? "#FEF3C7" : "#fff",
                border: `4px solid ${i % 3 === 0 ? "#FCD34D" : "#CBD5E1"}`,
                borderRadius: 18,
                fontFamily,
                fontWeight: 900,
                fontSize: 44,
                color: NAVY,
                boxShadow: "0 10px 26px rgba(23,35,59,0.18)",
                transform: `scale(${s}) rotate(${rot + wob * 0.6}deg)`,
                opacity: s > 0.01 ? 1 : 0,
              }}
            >
              {n} ?
            </div>
          );
        })}
      </AbsoluteFill>
      {/* overwhelmed: dim + big question mark */}
      <AbsoluteFill style={{ background: NAVY, opacity: dark * 0.88 }} />
      {dark > 0 && (
        <div
          style={{
            position: "absolute",
            width: "100%",
            top: 520,
            textAlign: "center",
            fontFamily,
            fontWeight: 900,
            fontSize: 520,
            color: "#fff",
            opacity: dark,
            transform: `scale(${0.6 + 0.4 * spring({ frame: f - c4, fps: 30, config: { damping: 7 } })}) rotate(${Math.sin(f / 6) * 4}deg)`,
          }}
        >
          ?
        </div>
      )}
      <Caption scene={scene} />
    </AbsoluteFill>
  );
};

// ================================================================ 2. intro
const Intro: React.FC<SceneProps> = ({ scene }) => {
  const f = useCurrentFrame();
  const blue = interpolate(f, [4, 26], [0, 1], clamp);
  const white = interpolate(f, [cap(scene, 1) - 18, cap(scene, 1) + 2], [0, 1], clamp);
  const logo = useSpring(cap(scene, 1) - 4, 10, 140);
  const dot = spring({ frame: f - cap(scene, 1) + 2, fps: 30, config: { damping: 6, stiffness: 200 } });
  const pill = useSpring(cap(scene, 1) + 14, 12);
  const pulse = 1 + 0.06 * spring({ frame: f - cap(scene, 2), fps: 30, config: { damping: 5 } }) * Math.max(0, 1 - (f - cap(scene, 2)) / 30);
  return (
    <AbsoluteFill style={{ background: NAVY }}>
      <div
        style={{
          position: "absolute",
          left: 540 - 1200 * blue,
          top: 860 - 1200 * blue,
          width: 2400 * blue,
          height: 2400 * blue,
          borderRadius: "50%",
          background: BLUE,
        }}
      />
      {f < cap(scene, 1) + 4 && blue > 0.95 && (
        <div style={{ position: "absolute", width: "100%", top: 700, textAlign: "center", fontFamily, fontWeight: 900, fontSize: 120, color: "#fff", letterSpacing: -3, opacity: interpolate(f, [26, 34], [0, 1], clamp) }}>
          그래서,
        </div>
      )}
      <div
        style={{
          position: "absolute",
          left: 540 - 1300 * white,
          top: 860 - 1300 * white,
          width: 2600 * white,
          height: 2600 * white,
          borderRadius: "50%",
          background: BG,
        }}
      />
      {white > 0.5 && (
        <AbsoluteFill style={{ alignItems: "center", paddingTop: 600 }}>
          <div style={{ transform: `scale(${(0.6 + 0.4 * logo) * pulse}) translateY(${(1 - logo) * 80}px)`, opacity: logo }}>
            <Logo size={250} dot={dot} />
          </div>
          <div style={{ marginTop: 40, fontFamily, fontWeight: 700, fontSize: 40, color: MUTED, opacity: interpolate(logo, [0.6, 1], [0, 1], clamp), letterSpacing: 1 }}>
            Matching Area, Talent &amp; Employment
          </div>
          <div
            style={{
              marginTop: 60,
              background: BLUE,
              color: "#fff",
              fontFamily,
              fontWeight: 900,
              fontSize: 56,
              padding: "22px 48px",
              borderRadius: 999,
              transform: `scale(${pill})`,
              boxShadow: "0 16px 40px rgba(37,99,235,0.4)",
            }}
          >
            나와 맞는 지역기업 찾기
          </div>
        </AbsoluteFill>
      )}
      <Caption scene={scene} hide={[1, 2]} />
    </AbsoluteFill>
  );
};

// ================================================================ 3. test flow on the real site
const Test: React.FC<SceneProps> = ({ scene }) => {
  const f = useCurrentFrame();
  const enter = useSpring(0, 15, 120);
  const qStart = cap(scene, 1);
  const T = taps as Record<string, number[]>;
  // basic info: tap three chips
  const steps: { at: number; img: string; tap?: string }[] = [
    { at: 0, img: "b0" },
    { at: 10, img: "b1", tap: "b1" },
    { at: 20, img: "b2", tap: "b2" },
    { at: 30, img: "b3", tap: "b3" },
  ];
  // 12 questions, 5 frames each
  const per = 5;
  for (let i = 0; i < 12; i++) {
    const n = `q${String(i + 1).padStart(2, "0")}`;
    steps.push({ at: qStart + i * per, img: n });
    steps.push({ at: qStart + i * per + 2, img: `${n}s`, tap: `${n}a` });
  }
  const cur = [...steps].reverse().find((s) => f >= s.at) ?? steps[0];
  const qNum = Math.min(12, Math.max(1, Math.floor((f - qStart) / per) + 1));
  const counter = useSpring(qStart - 2, 12);
  return (
    <AbsoluteFill>
      <Backdrop />
      <Label text="12문항 · 약 3분" />
      <Phone src={shot(cur.img)} y={290 + (1 - enter) * 1200} rotate={(1 - enter) * 6}>
        {steps
          .filter((s) => s.tap)
          .map((s) => (
            <Tap key={s.at} x={T[s.tap!][0]} y={T[s.tap!][1]} at={s.at} />
          ))}
      </Phone>
      {f >= qStart - 2 && (
        <div
          style={{
            position: "absolute",
            right: 40,
            top: 330,
            width: 210,
            height: 210,
            borderRadius: "50%",
            background: BLUE,
            color: "#fff",
            fontFamily,
            fontWeight: 900,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 16px 40px rgba(37,99,235,0.45)",
            transform: `scale(${counter * (f < qStart + 12 * per ? 1 + 0.05 * Math.sin(f) : 1)})`,
          }}
        >
          <div style={{ fontSize: 84, lineHeight: 1 }}>{String(qNum).padStart(2, "0")}</div>
          <div style={{ fontSize: 34, opacity: 0.85 }}>/ 12</div>
        </div>
      )}
      {f >= cap(scene, 2) - 3 && <Chip text="로그인 없이" icon={<LockIcon />} at={cap(scene, 2) - 3} x={40} y={1150} from={-1} />}
      {f >= cap(scene, 3) - 3 && <Chip text="약 3분" icon={<ClockIcon />} at={cap(scene, 3) - 3} x={660} y={1270} from={1} />}
      <Caption scene={scene} />
    </AbsoluteFill>
  );
};

// ================================================================ 4. match result
const Match: React.FC<SceneProps> = ({ scene }) => {
  const f = useCurrentFrame();
  const card1 = useSpring(4, 12);
  const card2 = useSpring(cap(scene, 1), 11);
  const arrow = interpolate(f, [cap(scene, 1) - 6, cap(scene, 1) + 6], [0, 1], clamp);
  const sparkle = useSpring(cap(scene, 2), 8);
  return (
    <AbsoluteFill>
      <Backdrop />
      <Label text="나의 유형 → 나의 기업" />
      <Phone src={shot("r0")} scale={0.92} y={300} />
      <AbsoluteFill style={{ background: "rgba(23,35,59,0.28)", opacity: card1 }} />
      {/* type card, enlarged from the result page */}
      <div
        style={{
          position: "absolute",
          left: 90,
          width: 900,
          top: 430,
          background: "#fff",
          borderRadius: 40,
          padding: "46px 54px",
          fontFamily,
          boxShadow: "0 30px 70px rgba(23,35,59,0.3)",
          transform: `scale(${0.7 + 0.3 * card1}) translateY(${(1 - card1) * 200}px)`,
          opacity: card1,
        }}
      >
        <div style={{ fontWeight: 700, fontSize: 38, color: BLUE }}>당신의 MATE 유형은</div>
        <div style={{ fontWeight: 900, fontSize: 92, color: NAVY, letterSpacing: -3, marginTop: 8 }}>글로벌 제품 설계자</div>
      </div>
      {/* arrow */}
      <svg style={{ position: "absolute", left: 500, top: 760 }} width={80} height={150} viewBox="0 0 80 150">
        <path d={`M40 0 V${120 * arrow}`} stroke={BLUE} strokeWidth={12} strokeLinecap="round" fill="none" />
        {arrow > 0.9 && <path d="M12 100 L40 135 L68 100" stroke={BLUE} strokeWidth={12} strokeLinecap="round" strokeLinejoin="round" fill="none" />}
      </svg>
      {/* company card */}
      <div
        style={{
          position: "absolute",
          left: 90,
          width: 900,
          top: 930,
          background: "#fff",
          borderRadius: 40,
          padding: "40px 50px",
          display: "flex",
          alignItems: "center",
          gap: 36,
          fontFamily,
          border: `6px solid ${BLUE}`,
          boxShadow: "0 30px 70px rgba(37,99,235,0.35)",
          transform: `scale(${card2})`,
          opacity: card2,
        }}
      >
        <Badge code="N" size={150} />
        <div>
          <div style={{ fontWeight: 900, fontSize: 80, color: NAVY, letterSpacing: -2 }}>넥센타이어</div>
          <div style={{ fontWeight: 700, fontSize: 38, color: MUTED }}>타이어·모빌리티 · 경남 양산</div>
        </div>
        <div
          style={{
            position: "absolute",
            right: -24,
            top: -36,
            background: BLUE,
            color: "#fff",
            fontWeight: 900,
            fontSize: 38,
            padding: "12px 28px",
            borderRadius: 999,
            transform: `scale(${sparkle}) rotate(6deg)`,
          }}
        >
          MATCH!
        </div>
      </div>
      <Caption scene={scene} />
    </AbsoluteFill>
  );
};

// ================================================================ 5. research: 10 companies, 9 criteria, TOP3
const CRITERIA = ["성장성", "기술력", "직무매력", "근무환경", "글로벌", "직원평가", "ESG", "정주 여건", "수익성"];
const TOP3 = [
  ["SW", "성우하이텍", 38],
  ["N", "넥센타이어", 37],
  ["PNC", "부산신항만", 36],
] as const;

const Research: React.FC<SceneProps> = ({ scene }) => {
  const f = useCurrentFrame();
  const c1 = cap(scene, 1);
  const c2 = cap(scene, 2);
  const c3 = cap(scene, 3);
  const team = useSpring(2, 12);
  const teamOut = interpolate(f, [c1 - 6, c1 + 4], [0, 1], clamp);
  const highlight = interpolate(f, [c2 - 4, c2 + 8], [0, 1], clamp);
  const gather = interpolate(f, [c2 + 18, c2 + 36], [0, 1], { ...clamp, easing: (t) => t * t * (3 - 2 * t) });
  const tilesAt = c2 + 34;
  const gridOut = interpolate(f, [c3 - 4, c3 + 8], [0, 1], clamp);
  const count = Math.round(interpolate(f, [c1, c1 + 40], [0, 60], clamp));
  return (
    <AbsoluteFill>
      <Backdrop />
      <Label text={scene.label} />
      {/* team badge */}
      {teamOut < 1 && (
        <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", opacity: 1 - teamOut, transform: `scale(${(0.7 + 0.3 * team) * (1 - 0.3 * teamOut)})` }}>
          <div style={{ width: 300, height: 300, borderRadius: "50%", background: "#fff", display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 24px 60px rgba(23,35,59,0.2)" }}>
            <SearchIcon size={170} />
          </div>
          <div style={{ marginTop: 50, fontFamily, fontWeight: 700, fontSize: 52, color: MUTED }}>부산대학교</div>
          <div style={{ fontFamily, fontWeight: 900, fontSize: 130, color: NAVY, letterSpacing: -4 }}>홈스윗홈</div>
        </AbsoluteFill>
      )}
      {/* the same mountain from the opening; the 10 picked ones light up and line up */}
      {f >= c1 - 4 && f < tilesAt + 8 && (
        <AbsoluteFill style={{ opacity: interpolate(f, [tilesAt, tilesAt + 8], [1, 0], clamp) }}>
          <Mountain start={c1 - 4} per={0.6} highlight={highlight} gather={gather} />
        </AbsoluteFill>
      )}
      {f >= c1 && f < c2 && (
        <div style={{ position: "absolute", top: 270, width: "100%", textAlign: "center", fontFamily, fontWeight: 900, fontSize: 96, color: NAVY, letterSpacing: -3, opacity: interpolate(f, [c2 - 8, c2], [1, 0], clamp) }}>
          {count}<span style={{ fontSize: 56 }}>여 곳</span>
        </div>
      )}
      {f >= c2 - 4 && f < c2 + 30 && (
        <div style={{ position: "absolute", top: 270, width: "100%", textAlign: "center", fontFamily, fontWeight: 900, fontSize: 96, color: BLUE, letterSpacing: -3, opacity: interpolate(f, [c2, c2 + 8, c2 + 22, c2 + 30], [0, 1, 1, 0], clamp) }}>
          10<span style={{ fontSize: 56 }}>곳 선정</span>
        </div>
      )}
      {/* 10 tiles */}
      {f >= tilesAt &&
        gridOut < 1 &&
        COMPANIES.map((c, i) => {
          const s = spring({ frame: f - tilesAt - i, fps: 30, config: { damping: 12, stiffness: 190 } });
          const col = i % 2;
          const row = Math.floor(i / 2);
          return (
            <div
              key={c[1]}
              style={{
                position: "absolute",
                left: col ? 555 : 65,
                top: 300 + row * 222 - gridOut * 120,
                transform: `scale(${(0.85 + 0.15 * s) * (1 - 0.4 * gridOut)})`,
                opacity: (1 - gridOut) * s,
              }}
            >
              <Tile c={c} w={460} />
            </div>
          );
        })}
      {/* criteria + scores */}
      {f >= c3 - 4 && (
        <>
          <div style={{ position: "absolute", top: 290, width: "100%", textAlign: "center", fontFamily, fontWeight: 900, fontSize: 64, color: NAVY, letterSpacing: -2, opacity: interpolate(f, [c3 - 4, c3 + 6], [0, 1], clamp) }}>
            9개 항목 · <span style={{ color: BLUE }}>45점</span> 만점 평가
          </div>
          <div style={{ position: "absolute", top: 410, left: 70, width: 940, display: "flex", flexWrap: "wrap", gap: 18, justifyContent: "center" }}>
            {CRITERIA.map((t, i) => {
              const s = spring({ frame: f - c3 - i * 2, fps: 30, config: { damping: 11, stiffness: 200 } });
              return (
                <div key={t} style={{ fontFamily, fontWeight: 900, fontSize: 42, color: BLUE, background: "#fff", border: `4px solid ${BLUE}`, borderRadius: 999, padding: "10px 28px", transform: `scale(${s})` }}>
                  {t}
                </div>
              );
            })}
          </div>
          {TOP3.map(([code, name, score], i) => {
            const st = c3 + 8 + i * 5;
            const grow = interpolate(f, [st, st + 20], [0, 1], { ...clamp, easing: (t) => 1 - Math.pow(1 - t, 3) });
            const s = spring({ frame: f - st + 4, fps: 30, config: { damping: 13 } });
            return (
              <div
                key={name}
                style={{
                  position: "absolute",
                  left: 70,
                  top: 720 + i * 210,
                  width: 940,
                  height: 180,
                  background: "#fff",
                  borderRadius: 34,
                  boxShadow: "0 14px 36px rgba(23,35,59,0.14)",
                  opacity: s,
                  transform: `translateX(${(1 - s) * -300}px)`,
                  fontFamily,
                  display: "flex",
                  alignItems: "center",
                  padding: "0 34px",
                  gap: 26,
                }}
              >
                <div style={{ fontWeight: 900, fontSize: 54, color: i === 0 ? BLUE : NAVY, width: 90 }}>{i + 1}위</div>
                <Badge code={code} size={96} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 900, fontSize: 44, color: NAVY }}>{name}</div>
                  <div style={{ marginTop: 12, height: 22, borderRadius: 11, background: SKY, overflow: "hidden" }}>
                    <div style={{ width: `${(score / 45) * 100 * grow}%`, height: "100%", background: BLUE, borderRadius: 11 }} />
                  </div>
                </div>
                <div style={{ fontWeight: 900, fontSize: 70, color: NAVY, width: 150, textAlign: "right" }}>
                  {Math.round(score * grow)}
                  <span style={{ fontSize: 30, color: MUTED }}>/45</span>
                </div>
              </div>
            );
          })}
        </>
      )}
      <Caption scene={scene} />
    </AbsoluteFill>
  );
};

// ================================================================ 6. ending
const Ending: React.FC<SceneProps> = ({ scene, dur }) => {
  const f = useCurrentFrame();
  const enter = useSpring(0, 15, 110);
  const logo = useSpring(cap(scene, 1) - 6, 10);
  const cta = useSpring(cap(scene, 2) - 4, 9);
  const scroll = interpolate(f, [10, dur], [0, 2600], { ...clamp, easing: (t) => t * t * (3 - 2 * t) });
  const press = cta > 0.9 ? 1 + 0.05 * Math.sin((f - cap(scene, 2)) / 3) : 1;
  return (
    <AbsoluteFill>
      <Backdrop />
      <div style={{ position: "absolute", top: 120, width: "100%", display: "flex", justifyContent: "center", transform: `scale(${0.5 + 0.5 * logo})`, opacity: logo }}>
        <Logo size={150} />
      </div>
      <Phone src={shot("home_full")} tall scroll={scroll} width={470} y={330 + (1 - enter) * 1100} rotate={(1 - enter) * -5} />
      {/* CTA + address */}
      <div style={{ position: "absolute", top: 1170, width: "100%", display: "flex", flexDirection: "column", alignItems: "center", transform: `scale(${cta * press})`, opacity: cta }}>
        <div style={{ background: BLUE, color: "#fff", fontFamily, fontWeight: 900, fontSize: 62, padding: "26px 60px", borderRadius: 999, boxShadow: "0 20px 50px rgba(37,99,235,0.5)", display: "flex", alignItems: "center", gap: 18 }}>
          내 MATE 찾기 <span style={{ fontSize: 60 }}>→</span>
        </div>
        <div style={{ marginTop: 22, background: "#fff", color: NAVY, fontFamily, fontWeight: 700, fontSize: 30, padding: "12px 28px", borderRadius: 18, boxShadow: "0 10px 26px rgba(23,35,59,0.15)" }}>
          mate-pnu-homesweethome.fondcinch.chatgpt.site
        </div>
      </div>
      <Caption scene={scene} />
    </AbsoluteFill>
  );
};

// ================================================================ composition
const SCENES: Record<string, React.FC<SceneProps>> = {
  hook: Hook,
  intro: Intro,
  test: Test,
  match: Match,
  research: Research,
  ending: Ending,
};

export const Mate: React.FC = () => (
  <AbsoluteFill style={{ background: BG }}>
    {timing.scenes.map((s) => {
      const Comp = SCENES[s.id];
      return (
        <Sequence key={s.id} from={s.from} durationInFrames={s.frames} name={s.id}>
          <Comp scene={s} dur={s.frames} />
          <Audio src={staticFile(s.audio)} />
        </Sequence>
      );
    })}
  </AbsoluteFill>
);
