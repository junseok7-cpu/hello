import React from "react";
import {
  AbsoluteFill,
  Audio,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import timing from "./timing.json";
import { Bowl, Buckwheat, C, Cow, Defs, FlourSack, Person, Pin, Ship, Shed, Sitter } from "../common/art";
import { Camera, Captions, Label, Vignette, clamp, fontFamily, loadFonts } from "../common/ui";

loadFonts();

type Scene = (typeof timing.scenes)[number];
type SceneProps = { scene: Scene; dur: number };
const FADE = 10;

/** frame at which caption i starts (relative to the scene) */
const cap = (scene: Scene, i: number) => scene.captions[Math.min(i, scene.captions.length - 1)].from;

const Svg: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <svg viewBox="0 0 1080 1920" width={1080} height={1920} style={{ position: "absolute" }}>
    <Defs />
    {children}
  </svg>
);

const Sky: React.FC<{ top: string; bottom: string; sun?: string; sunY?: number }> = ({ top, bottom, sun, sunY = 760 }) => (
  <AbsoluteFill style={{ background: `linear-gradient(180deg, ${top} 0%, ${bottom} 70%)` }}>
    {sun && (
      <div
        style={{
          position: "absolute",
          left: 540 - 170,
          top: sunY - 170,
          width: 340,
          height: 340,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${sun} 0%, ${sun} 45%, rgba(255,255,255,0) 70%)`,
        }}
      />
    )}
  </AbsoluteFill>
);

// ================================================================ 1. hook
const Hook: React.FC<SceneProps> = ({ scene, dur }) => {
  const f = useCurrentFrame();
  const swap = cap(scene, 1);
  const cowOut = interpolate(f, [swap - 6, swap + 6], [1, 0], clamp);
  const manIn = interpolate(f, [swap, swap + 10], [0, 1], clamp);
  const q = spring({ frame: f - cap(scene, 2), fps: 30, config: { damping: 8 } });
  return (
    <AbsoluteFill>
      <Sky top="#F7D9A8" bottom="#E89452" sun="#FFF1C9" sunY={700} />
      <Camera duration={dur} from={1.28} to={1.42} originY="60%">
        <Svg>
          <rect x={0} y={1130} width={1080} height={800} fill="#B9844F" />
          <Shed x={110} y={1130} w={860} h={300} doors={4} lit={[0, manIn, 0, 0]} />
          <g opacity={cowOut}>
            <Cow x={425} y={1128} s={0.9} step={f} />
          </g>
          <g opacity={manIn}>
            <Person x={400} y={1128} s={1.1} step={0} coat="#6F5D4E" />
          </g>
          <text
            x={720}
            y={760}
            textAnchor="middle"
            fontFamily="Pretendard"
            fontWeight={900}
            fontSize={260}
            fill="#FFF4E2"
            stroke="#15110E"
            strokeWidth={14}
            paintOrder="stroke"
            opacity={Math.min(q, 1)}
            transform={`rotate(${(1 - q) * -20} 720 700)`}
          >
            ?
          </text>
        </Svg>
      </Camera>
      <Label text={scene.label} delay={cap(scene, 2)} />
    </AbsoluteFill>
  );
};

// ================================================================ 2. 1909 quarantine sheds
const Y1909: React.FC<SceneProps> = ({ scene, dur }) => {
  const f = useCurrentFrame();
  const shipIn = spring({ frame: f - cap(scene, 3), fps: 30, config: { damping: 18 } });
  const tag = spring({ frame: f - cap(scene, 5), fps: 30, config: { damping: 10 } });
  const sheds = [0, 1, 2, 3, 4];
  return (
    <AbsoluteFill>
      <Sky top="#CFE3E8" bottom="#F3DDB5" />
      <Camera duration={dur} from={1.25} to={1.32} originY="55%">
        <Svg>
          {/* hills + ground + sea */}
          <path d="M 0 760 Q 250 620 520 720 Q 800 600 1080 700 L 1080 1100 L 0 1100 Z" fill="#9DB08A" />
          <rect x={0} y={860} width={1080} height={260} fill="#CDB487" />
          <rect x={0} y={1110} width={1080} height={820} fill="#4E7FA0" />
          {[0, 1, 2, 3].map((i) => (
            <rect key={i} x={((f * 2 + i * 300) % 1300) - 200} y={1150 + i * 40} width={140} height={6} rx={3} fill="#9CC3D9" opacity={0.6} />
          ))}
          {/* two rows of quarantine sheds, popping in */}
          {sheds.map((i) => {
            const p = spring({ frame: f - 6 - i * 7, fps: 30, config: { damping: 13 } });
            return (
              <g key={`b${i}`} transform={`translate(0,${(1 - p) * 40})`} opacity={Math.min(p * 1.5, 1)}>
                <Shed x={40 + i * 205} y={890} w={170} h={70} doors={2} />
              </g>
            );
          })}
          {sheds.map((i) => {
            const p = spring({ frame: f - 30 - i * 7, fps: 30, config: { damping: 13 } });
            return (
              <g key={`f${i}`} transform={`translate(0,${(1 - p) * 40})`} opacity={Math.min(p * 1.5, 1)}>
                <Shed x={20 + i * 215} y={1010} w={190} h={85} doors={2} />
              </g>
            );
          })}
          {/* cows walking along the road */}
          {[0, 1, 2, 3].map((i) => (
            <Cow key={i} x={-150 + f * 3.2 - i * 170} y={1085} s={0.55} step={f + i * 7} />
          ))}
          {/* ship to Japan */}
          <g transform={`translate(${(1 - shipIn) * 700},0)`}>
            <Ship x={700} y={1200} s={0.8} t={f} />
            <g opacity={shipIn}>
              <rect x={540} y={1010} width={320} height={70} rx={35} fill="#FFF4E2" stroke={C.ink} strokeWidth={5} />
              <text x={700} y={1060} textAnchor="middle" fontFamily="Pretendard" fontWeight={900} fontSize={44} fill={C.ink}>
                일본·만주로 →
              </text>
            </g>
          </g>
          {/* tag: 소막 */}
          <g transform={`translate(540,700) scale(${tag})`} opacity={Math.min(tag, 1)}>
            <rect x={-250} y={-70} width={500} height={120} rx={60} fill="#D9442E" stroke={C.ink} strokeWidth={6} />
            <text x={0} y={14} textAnchor="middle" fontFamily="Pretendard" fontWeight={900} fontSize={62} fill="#FFF4E2">
              소막 = 소의 막사
            </text>
          </g>
        </Svg>
      </Camera>
      <Label text={scene.label} />
    </AbsoluteFill>
  );
};

// ================================================================ 3. 1950 refugees
const Y1950: React.FC<SceneProps> = ({ scene, dur }) => {
  const f = useCurrentFrame();
  const homeAt = cap(scene, 2);
  const lit = (k: number) => interpolate(f, [homeAt + k * 4, homeAt + k * 4 + 8], [0, 1], clamp);
  const people = [
    { d: 0, coat: "#6F5D4E" },
    { d: 70, coat: "#5B6470", child: true },
    { d: 130, coat: "#7A5A48" },
    { d: 200, coat: "#4F5A4A" },
    { d: 260, coat: "#806A55", child: true },
    { d: 320, coat: "#5E5048" },
  ];
  return (
    <AbsoluteFill>
      <Sky top="#2E3B5C" bottom="#B07A6A" sun="#F5C98A" sunY={900} />
      <Camera duration={dur} from={1.3} to={1.4} originY="58%">
        <Svg>
          <rect x={0} y={1000} width={1080} height={920} fill="#5D4A3E" />
          <Shed x={-40} y={880} w={520} h={150} doors={4} lit={[0, 1, 2, 3].map((k) => lit(k))} roof="#34323A" smoke={f} />
          <Shed x={560} y={880} w={560} h={150} doors={4} lit={[0, 1, 2, 3].map((k) => lit(k + 4))} roof="#34323A" />
          <Shed x={60} y={1010} w={960} h={190} doors={6} lit={[0, 1, 2, 3, 4, 5].map((k) => lit(k + 2))} roof="#2E2C33" smoke={f + 30} />
          {people.map((p, i) => (
            <Person key={i} x={-120 + f * 4.2 - p.d} y={1170} s={0.95} step={f + i * 5} coat={p.coat} child={p.child} />
          ))}
        </Svg>
      </Camera>
      <Label text={scene.label} />
    </AbsoluteFill>
  );
};

// ================================================================ 4. inside: cross-section + zoom circle
const Inside: React.FC<SceneProps> = ({ scene, dur }) => {
  const f = useCurrentFrame();
  const rooms = 12;
  const x0 = 70;
  const w = 940;
  const rw = w / rooms;
  const top = 930;
  const bottom = 1200;
  const zoom = spring({ frame: f - cap(scene, 1), fps: 30, config: { damping: 14 } });
  const target = 4; // room shown in the zoom circle
  const tx = x0 + rw * (target + 0.5);
  const cx = 600;
  const cy = 640;
  return (
    <AbsoluteFill>
      <Sky top="#3B2C2A" bottom="#7C5236" />
      <Camera duration={dur} from={1.0} to={1.05} originY="55%">
        <Svg>
          {/* roof band and outer shell, cut open */}
          <polygon points={`${x0 - 30},${top} ${x0 + w + 30},${top} ${x0 + w - 20},${top - 110} ${x0 + 20},${top - 110}`} fill={C.roof} />
          <rect x={x0} y={top} width={w} height={bottom - top} fill="#E9D3AE" />
          <rect x={x0} y={bottom} width={w} height={26} fill={C.woodDark} />
          <rect x={x0 - 12} y={top} width={12} height={bottom - top + 26} fill={C.wood} />
          <rect x={x0 + w} y={top} width={12} height={bottom - top + 26} fill={C.wood} />
          {/* rooms appear one by one */}
          {Array.from({ length: rooms }).map((_, i) => {
            const t = interpolate(f, [6 + i * 5, 16 + i * 5], [0, 1], clamp);
            const rx = x0 + i * rw;
            return (
              <g key={i}>
                <rect x={rx} y={top} width={rw} height={(bottom - top) * t} fill={i % 2 ? "#E2C79C" : "#EED9B6"} />
                <circle cx={rx + rw / 2} cy={top + 34} r={22} fill={C.lamp} opacity={0.5 * t} />
                <circle cx={rx + rw / 2} cy={top + 34} r={8} fill={C.lamp} opacity={t} />
                <g opacity={t}>
                  <Sitter x={rx + rw * 0.33} y={bottom} s={0.75} />
                  <Sitter x={rx + rw * 0.7} y={bottom} s={i % 3 === 0 ? 0.55 : 0.7} color="#4A3B30" />
                </g>
                {i > 0 && (
                  <rect x={rx - 4} y={top + (bottom - top) * (1 - t)} width={8} height={(bottom - top) * t} fill={C.woodDark} />
                )}
              </g>
            );
          })}
          {/* highlight the room + connector lines */}
          <g opacity={Math.min(zoom, 1)}>
            <rect x={tx - rw / 2} y={top} width={rw} height={bottom - top} fill="none" stroke="#FFF4E2" strokeWidth={6} />
            <line x1={tx - rw / 2} y1={top} x2={cx - 200} y2={cy + 110} stroke="#FFF4E2" strokeWidth={4} />
            <line x1={tx + rw / 2} y1={top} x2={cx + 200} y2={cy + 110} stroke="#FFF4E2" strokeWidth={4} />
          </g>
          {/* zoom circle: one family's room */}
          <g transform={`translate(${cx},${cy}) scale(${zoom})`}>
            <circle r={238} fill="#FFF4E2" />
            <g clipPath="url(#zoomClip)">
              <rect x={-240} y={-240} width={480} height={480} fill="#EED9B6" />
              <rect x={-240} y={110} width={480} height={140} fill="#B98A5A" />
              {[-160, -60, 40, 140].map((x) => (
                <line key={x} x1={x} y1={-240} x2={x} y2={110} stroke="#D7BC92" strokeWidth={4} />
              ))}
              <circle cx={0} cy={-150} r={60} fill={C.lamp} opacity={0.35} />
              <circle cx={0} cy={-150} r={18} fill={C.lamp} />
              <line x1={0} y1={-240} x2={0} y2={-168} stroke={C.ink} strokeWidth={3} />
              {/* low table with bowls */}
              <rect x={-110} y={70} width={220} height={22} rx={8} fill="#6B4024" />
              <rect x={-90} y={92} width={14} height={36} fill="#55331C" />
              <rect x={76} y={92} width={14} height={36} fill="#55331C" />
              <ellipse cx={-40} cy={62} rx={30} ry={12} fill="#F3F0EA" />
              <ellipse cx={40} cy={62} rx={30} ry={12} fill="#F3F0EA" />
              <Sitter x={-160} y={150} s={1.5} color="#4A3B30" />
              <Sitter x={160} y={150} s={1.4} color="#3A2E26" />
              <Sitter x={0} y={160} s={0.9} color="#5A4637" />
            </g>
            <circle r={238} fill="none" stroke={C.ink} strokeWidth={14} />
            <circle r={238} fill="none" stroke="#FFF4E2" strokeWidth={6} />
          </g>
        </Svg>
      </Camera>
      <Label text={scene.label} />
    </AbsoluteFill>
  );
};

// ================================================================ 5. flour instead of buckwheat
const Flour: React.FC<SceneProps> = ({ scene }) => {
  const f = useCurrentFrame();
  const rare = interpolate(f, [cap(scene, 1), cap(scene, 1) + 12], [0, 1], clamp);
  const sack = spring({ frame: f - cap(scene, 2), fps: 30, config: { damping: 9, mass: 0.9 } });
  const dust = interpolate(f, [cap(scene, 2) + 8, cap(scene, 2) + 40], [0, 1], clamp);
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ background: "radial-gradient(circle at 50% 45%, #FBF1DE 0%, #EBCB98 100%)" }} />
      <Svg>
        {/* buckwheat */}
        <Buckwheat x={270} y={1080} s={1.9} grey={rare} />
        <text x={270} y={1180} textAnchor="middle" fontFamily="Pretendard" fontWeight={900} fontSize={72} fill={C.ink}>
          메밀
        </text>
        <g opacity={rare}>
          <line x1={110} y1={540} x2={110 + 320 * rare} y2={540 + 460 * rare} stroke="#D9442E" strokeWidth={22} strokeLinecap="round" />
          <line x1={430} y1={540} x2={430 - 320 * rare} y2={540 + 460 * rare} stroke="#D9442E" strokeWidth={22} strokeLinecap="round" />
        </g>
        {/* flour sack drops in */}
        <g transform={`translate(0,${(1 - sack) * -1500})`} opacity={f >= cap(scene, 2) ? 1 : 0}>
          <FlourSack x={790} y={1150} s={1.3} label="밀가루" />
        </g>
        {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
          <circle
            key={i}
            cx={790 + Math.cos(i) * 180 * dust}
            cy={1110 - Math.abs(Math.sin(i * 1.7)) * 120 * dust}
            r={20 + 30 * dust}
            fill="#FFFFFF"
            opacity={0.7 * (1 - dust) * (dust > 0 ? 1 : 0)}
          />
        ))}
      </Svg>
      <Label text={scene.label} />
    </AbsoluteFill>
  );
};

// ================================================================ 6. birth of milmyeon
const Milmyeon6: React.FC<SceneProps> = ({ scene, dur }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const merge = interpolate(f, [18, 50], [0, 1], clamp);
  const dough = spring({ frame: f - 46, fps, config: { damping: 9 } });
  const pressAt = cap(scene, 1);
  const noodle = interpolate(f, [pressAt, pressAt + 30], [0, 1], clamp);
  const bowlIn = spring({ frame: f - pressAt + 6, fps, config: { damping: 14 } });
  const topAt = cap(scene, 2);
  const tops = [0, 1, 2, 3].map((k) => spring({ frame: f - topAt - k * 6, fps, config: { damping: 12 } }));
  const pin = spring({ frame: f - cap(scene, 4) + 4, fps, config: { damping: 9 } });
  const doughOut = interpolate(f, [pressAt + 24, pressAt + 34], [1, 0], clamp);
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ background: "radial-gradient(circle at 50% 55%, #FFE2B0 0%, #E98E4A 100%)" }} />
      <Camera duration={dur} from={1.0} to={1.05} originY="60%">
        <Svg>
          {/* ingredients merge */}
          <g opacity={1 - merge}>
            <g transform={`translate(${-220 * (1 - merge) + 540 - 540 * (1 - merge)},0)`}>
              <FlourSack x={270 + 250 * merge} y={980} s={0.95} />
            </g>
            <g transform={`translate(${-250 * merge},0)`}>
              <ellipse cx={790} cy={890} rx={130} ry={30} fill="#D8D4CF" />
              <path d="M 660 890 Q 680 960 790 966 Q 900 960 920 890 Z" fill="#CFCAC4" />
              <path d="M 700 890 Q 790 800 880 890 Z" fill="#FFFFFF" />
              <text x={790} y={1030} textAnchor="middle" fontFamily="Pretendard" fontWeight={900} fontSize={52} fill={C.ink}>
                전분
              </text>
            </g>
            <text x={540} y={860} textAnchor="middle" fontFamily="Pretendard" fontWeight={900} fontSize={110} fill="#FFF4E2" stroke={C.ink} strokeWidth={10} paintOrder="stroke">
              +
            </text>
          </g>
          {/* dough ball */}
          <g opacity={doughOut} transform={`translate(540,${700 - 20 * noodle}) scale(${dough})`}>
            <circle r={110} fill="#F3E3BE" stroke="#D6BF8C" strokeWidth={6} />
            <ellipse cx={-30} cy={-40} rx={36} ry={20} fill="#FFF6DF" />
          </g>
          {/* strands falling into the bowl */}
          {Array.from({ length: 9 }).map((_, i) => (
            <line
              key={i}
              x1={460 + i * 20}
              x2={460 + i * 20 + Math.sin(f * 0.2 + i) * 6}
              y1={760}
              y2={760 + 300 * noodle}
              stroke="#F1E2B8"
              strokeWidth={9}
              strokeLinecap="round"
              opacity={noodle * (1 - tops[0])}
            />
          ))}
          <g transform={`translate(0,${(1 - bowlIn) * 400})`} opacity={Math.min(bowlIn, 1)}>
            <Bowl x={540} y={1100} s={1.4} fill={noodle} toppings={tops} steam={f} />
          </g>
          {/* pin: Uam-dong */}
          <g opacity={Math.min(pin, 1)}>
            <Pin x={830} y={860} s={pin * 1.15} text="우암동" />
          </g>
        </Svg>
      </Camera>
      <Label text={scene.label} />
    </AbsoluteFill>
  );
};

// ================================================================ 7. ending
const Ending: React.FC<SceneProps> = ({ scene, dur }) => {
  const f = useCurrentFrame();
  const sub = interpolate(f, [cap(scene, 1), cap(scene, 1) + 15], [0, 1], clamp);
  const roofs = ["#3E5C8A", "#8A3E3E", "#3E7A5C", "#6B5B8A", "#8A6A3E"];
  return (
    <AbsoluteFill>
      <Sky top="#F2B48A" bottom="#7A4A6A" sun="#FFE3B0" sunY={820} />
      <Camera duration={dur} from={1.45} to={1.3} originY="58%">
        <Svg>
          <rect x={0} y={1060} width={1080} height={860} fill="#4A3440" />
          {roofs.map((r, i) => (
            <Shed key={i} x={-60 + i * 240} y={960 + (i % 2) * 20} w={230} h={110} doors={2} roof={r} wall="#9A7A5C" lit={[0.9, 0.6]} />
          ))}
          {roofs.map((r, i) => (
            <Shed key={`n${i}`} x={-160 + i * 300} y={1090} w={280} h={130} doors={2} roof={roofs[(i + 2) % 5]} wall="#8E6E52" lit={[0.7, 1]} smoke={i === 2 ? f : undefined} />
          ))}
          <Bowl x={540} y={1190} s={0.5} steam={f} />
        </Svg>
      </Camera>
      <Label text={scene.label} />
      <div
        style={{
          position: "absolute",
          top: 330,
          width: "100%",
          textAlign: "center",
          fontFamily,
          fontWeight: 700,
          fontSize: 50,
          color: "#FFF4E2",
          WebkitTextStroke: "10px #15110E",
          paintOrder: "stroke fill",
          opacity: sub,
          transform: `translateY(${(1 - sub) * 20}px)`,
        }}
      >
        피란수도 부산의 유산
      </div>
    </AbsoluteFill>
  );
};

const SCENES: Record<string, React.FC<SceneProps>> = {
  hook: Hook,
  "1909": Y1909,
  "1950": Y1950,
  inside: Inside,
  flour: Flour,
  milmyeon: Milmyeon6,
  ending: Ending,
};

const Fade: React.FC<{ children: React.ReactNode; first: boolean }> = ({ children, first }) => {
  const f = useCurrentFrame();
  const o = first ? 1 : interpolate(f, [0, FADE], [0, 1], clamp);
  return <AbsoluteFill style={{ opacity: o }}>{children}</AbsoluteFill>;
};

export const Milmyeon: React.FC = () => (
  <AbsoluteFill style={{ background: "#15110E" }}>
    {timing.scenes.map((scene, i) => {
      const Comp = SCENES[scene.id];
      const last = i === timing.scenes.length - 1;
      const dur = scene.frames + (last ? 0 : FADE);
      return (
        <Sequence key={scene.id} from={scene.from} durationInFrames={dur} name={scene.id}>
          <Fade first={i === 0}>
            <Comp scene={scene} dur={dur} />
            <Vignette />
            <Captions captions={scene.captions} />
          </Fade>
        </Sequence>
      );
    })}
    {timing.scenes.map((scene) => (
      <Sequence key={`a-${scene.id}`} from={scene.from} durationInFrames={scene.frames} layout="none">
        <Audio src={staticFile(scene.audio)} />
      </Sequence>
    ))}
  </AbsoluteFill>
);
