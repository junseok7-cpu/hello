/* SVG illustration parts. All return <g> to be placed inside a 1080x1920 <svg>. */
import React from "react";

export const C = {
  wood: "#8A5A36",
  woodDark: "#5E3B22",
  roof: "#3F3B40",
  roofEdge: "#2A272C",
  cow: "#A65B2E",
  cowDark: "#7A3F1D",
  lamp: "#FFD27A",
  skin: "#F0C49A",
  cloth: "#E9E0CF",
  ink: "#1C1714",
};

// ---------------------------------------------------------------- long cattle shed (side)
export const Shed: React.FC<{
  x: number;
  y: number; // bottom of the wall
  w: number;
  h: number;
  doors?: number;
  lit?: number[]; // 0..1 per door, warm window glow
  roof?: string;
  wall?: string;
  smoke?: number; // frame for smoke animation; undefined = no smoke
}> = ({ x, y, w, h, doors = 5, lit = [], roof = C.roof, wall = C.wood, smoke }) => {
  const top = y - h;
  const roofH = h * 0.75;
  const planks = Math.floor(w / 22);
  return (
    <g>
      {/* shadow */}
      <ellipse cx={x + w / 2} cy={y + 6} rx={w * 0.55} ry={14} fill="rgba(0,0,0,0.25)" />
      {/* wall */}
      <rect x={x} y={top} width={w} height={h} fill={wall} />
      {Array.from({ length: planks }).map((_, i) => (
        <line
          key={i}
          x1={x + (i + 0.5) * (w / planks)}
          x2={x + (i + 0.5) * (w / planks)}
          y1={top}
          y2={y}
          stroke={C.woodDark}
          strokeWidth={2}
          opacity={0.55}
        />
      ))}
      {/* doors / windows */}
      {Array.from({ length: doors }).map((_, i) => {
        const dw = (w / doors) * 0.38;
        const dx = x + (i + 0.5) * (w / doors) - dw / 2;
        const l = lit[i] ?? 0;
        return (
          <g key={i}>
            {l > 0 && (
              <rect
                x={dx - 14}
                y={top + h * 0.25 - 14}
                width={dw + 28}
                height={h * 0.75 + 14}
                fill={C.lamp}
                opacity={0.25 * l}
                rx={10}
              />
            )}
            <rect x={dx} y={top + h * 0.25} width={dw} height={h * 0.75} fill={C.woodDark} />
            <rect
              x={dx + 4}
              y={top + h * 0.25 + 4}
              width={dw - 8}
              height={h * 0.75 - 4}
              fill={C.lamp}
              opacity={l}
            />
          </g>
        );
      })}
      {/* roof: side view of a gable roof */}
      <polygon
        points={`${x - 18},${top + 4} ${x + w + 18},${top + 4} ${x + w - 30},${top - roofH} ${x + 30},${top - roofH}`}
        fill={roof}
      />
      <rect x={x - 22} y={top - 2} width={w + 44} height={12} fill={C.roofEdge} rx={3} />
      {Array.from({ length: Math.floor(w / 60) }).map((_, i) => (
        <line
          key={i}
          x1={x + 10 + i * 60}
          x2={x + 30 + i * 60 * 0.96}
          y1={top}
          y2={top - roofH + 6}
          stroke={C.roofEdge}
          strokeWidth={3}
          opacity={0.5}
        />
      ))}
      {smoke !== undefined &&
        [0, 1, 2].map((k) => {
          const t = ((smoke + k * 25) % 75) / 75;
          return (
            <circle
              key={k}
              cx={x + w * 0.7 + Math.sin(t * 6) * 10}
              cy={top - roofH - 10 - t * 120}
              r={14 + t * 22}
              fill="#EDE6DA"
              opacity={0.55 * (1 - t)}
            />
          );
        })}
    </g>
  );
};

// ---------------------------------------------------------------- cow (side, facing right)
export const Cow: React.FC<{ x: number; y: number; s?: number; step?: number; flip?: boolean }> = ({
  x,
  y,
  s = 1,
  step = 0,
  flip = false,
}) => {
  const leg = (phase: number) => Math.sin(step * 0.35 + phase) * 8;
  return (
    <g transform={`translate(${x},${y}) scale(${flip ? -s : s},${s})`}>
      <ellipse cx={0} cy={4} rx={70} ry={10} fill="rgba(0,0,0,0.22)" />
      {/* legs */}
      {[
        [-45, 0],
        [-28, Math.PI],
        [30, Math.PI],
        [46, 0],
      ].map(([lx, ph], i) => (
        <rect
          key={i}
          x={lx - 7}
          y={-48}
          width={14}
          height={50}
          rx={5}
          fill={i % 2 ? C.cowDark : C.cow}
          transform={`rotate(${leg(ph)} ${lx} -48)`}
        />
      ))}
      {/* body */}
      <rect x={-68} y={-110} width={136} height={70} rx={34} fill={C.cow} />
      {/* tail */}
      <path d="M -66 -95 Q -88 -70 -80 -45" stroke={C.cowDark} strokeWidth={6} fill="none" />
      {/* head */}
      <g transform={`translate(70,-112) rotate(${Math.sin(step * 0.18) * 4})`}>
        <rect x={-6} y={-6} width={44} height={56} rx={18} fill={C.cow} />
        <rect x={6} y={28} width={36} height={24} rx={12} fill="#C98B67" />
        <circle cx={20} cy={10} r={4} fill={C.ink} />
        <path d="M -2 -2 Q -14 -24 -2 -30" stroke="#EADBC2" strokeWidth={7} fill="none" strokeLinecap="round" />
        <path d="M 30 -2 Q 44 -22 34 -30" stroke="#EADBC2" strokeWidth={7} fill="none" strokeLinecap="round" />
        <ellipse cx={-10} cy={6} rx={12} ry={7} fill={C.cowDark} />
      </g>
    </g>
  );
};

// ---------------------------------------------------------------- refugee (walking, bundle)
export const Person: React.FC<{
  x: number;
  y: number;
  s?: number;
  step?: number;
  coat?: string;
  bundle?: string;
  child?: boolean;
}> = ({ x, y, s = 1, step = 0, coat = "#7D6B5A", bundle = "#C9B28A", child = false }) => {
  const sc = child ? s * 0.7 : s;
  const bob = Math.abs(Math.sin(step * 0.3)) * 4;
  const leg = Math.sin(step * 0.3) * 14;
  return (
    <g transform={`translate(${x},${y - bob}) scale(${sc})`}>
      <ellipse cx={0} cy={bob + 2} rx={30} ry={6} fill="rgba(0,0,0,0.25)" />
      <rect x={-12} y={-60} width={11} height={60} rx={5} fill="#4B3F36" transform={`rotate(${leg} -6 -60)`} />
      <rect x={2} y={-60} width={11} height={60} rx={5} fill="#3E342C" transform={`rotate(${-leg} 8 -60)`} />
      <path d="M -26 -60 L -18 -140 L 18 -140 L 26 -60 Z" fill={coat} />
      <circle cx={0} cy={-162} r={22} fill={C.skin} />
      <path d="M -22 -166 Q 0 -196 22 -166 Z" fill="#2E2620" />
      {/* bundle on the back */}
      <rect x={-52} y={-150} width={38} height={46} rx={12} fill={bundle} />
      <line x1={-33} y1={-150} x2={-33} y2={-104} stroke="#8E7652" strokeWidth={4} />
    </g>
  );
};

// ---------------------------------------------------------------- simple seated silhouette
export const Sitter: React.FC<{ x: number; y: number; s?: number; color?: string }> = ({
  x,
  y,
  s = 1,
  color = "#3A2E26",
}) => (
  <g transform={`translate(${x},${y}) scale(${s})`}>
    <circle cx={0} cy={-58} r={14} fill={color} />
    <path d="M -20 0 Q -20 -42 0 -42 Q 20 -42 20 0 Z" fill={color} />
  </g>
);

// ---------------------------------------------------------------- ship
export const Ship: React.FC<{ x: number; y: number; s?: number; t?: number }> = ({ x, y, s = 1, t = 0 }) => (
  <g transform={`translate(${x},${y + Math.sin(t * 0.08) * 4}) scale(${s})`}>
    <path d="M -170 0 L 170 0 L 130 60 L -140 60 Z" fill="#2F3440" />
    <rect x={-110} y={-50} width={170} height={50} fill="#D9D2C3" />
    <rect x={20} y={-110} width={34} height={64} fill="#8C3B2E" />
    {[0, 1, 2, 3].map((i) => (
      <rect key={i} x={-96 + i * 36} y={-36} width={20} height={16} fill="#5D6475" />
    ))}
    {[0, 1, 2].map((k) => {
      const p = ((t + k * 20) % 60) / 60;
      return <circle key={k} cx={40 - p * 60} cy={-120 - p * 90} r={14 + p * 18} fill="#CFC8BC" opacity={0.6 * (1 - p)} />;
    })}
  </g>
);

// ---------------------------------------------------------------- flour sack (generic relief flour)
export const FlourSack: React.FC<{ x: number; y: number; s?: number; label?: string }> = ({
  x,
  y,
  s = 1,
  label = "밀가루",
}) => (
  <g transform={`translate(${x},${y}) scale(${s})`}>
    <ellipse cx={0} cy={6} rx={150} ry={20} fill="rgba(0,0,0,0.25)" />
    <path d="M -130 0 Q -150 -150 -110 -280 L 110 -280 Q 150 -150 130 0 Z" fill="#F3EBDD" stroke="#CBBFA8" strokeWidth={4} />
    <path d="M -110 -280 Q -60 -320 0 -296 Q 60 -320 110 -280" fill="#E7DCC8" stroke="#CBBFA8" strokeWidth={4} />
    <rect x={-120} y={-292} width={240} height={14} rx={7} fill="#B8A584" />
    <rect x={-92} y={-200} width={184} height={110} rx={10} fill="none" stroke="#3B5B8C" strokeWidth={6} />
    <text x={0} y={-128} textAnchor="middle" fontFamily="Pretendard" fontWeight={900} fontSize={54} fill="#3B5B8C">
      {label}
    </text>
    <text x={0} y={-100} textAnchor="middle" fontFamily="Pretendard" fontWeight={700} fontSize={22} fill="#3B5B8C">
      RELIEF FLOUR
    </text>
  </g>
);

// ---------------------------------------------------------------- buckwheat stalk
export const Buckwheat: React.FC<{ x: number; y: number; s?: number; grey?: number }> = ({ x, y, s = 1, grey = 0 }) => (
  <g transform={`translate(${x},${y}) scale(${s})`} style={{ filter: `grayscale(${grey})` }} opacity={1 - grey * 0.4}>
    <path d="M 0 0 Q -6 -120 4 -260" stroke="#B4486A" strokeWidth={8} fill="none" />
    <path d="M 2 -150 Q 50 -180 70 -230" stroke="#B4486A" strokeWidth={6} fill="none" />
    <path d="M 0 -110 Q -50 -140 -66 -190" stroke="#B4486A" strokeWidth={6} fill="none" />
    <path d="M 0 -60 Q 40 -60 60 -40 Q 30 -20 0 -60" fill="#6E9B4E" />
    {[
      [4, -270],
      [72, -240],
      [-68, -200],
      [20, -240],
      [-14, -250],
      [58, -255],
      [-50, -215],
    ].map(([cx, cy], i) => (
      <g key={i}>
        {[0, 72, 144, 216, 288].map((a) => (
          <circle
            key={a}
            cx={cx + Math.cos((a * Math.PI) / 180) * 9}
            cy={cy + Math.sin((a * Math.PI) / 180) * 9}
            r={8}
            fill="#FBF6F0"
          />
        ))}
        <circle cx={cx} cy={cy} r={5} fill="#E9B4C4" />
      </g>
    ))}
  </g>
);

// ---------------------------------------------------------------- bowl of milmyeon
export const Bowl: React.FC<{
  x: number;
  y: number;
  s?: number;
  fill?: number; // 0..1 broth + noodles
  toppings?: number[]; // 0..1 each: sauce, cucumber, meat, egg
  steam?: number;
}> = ({ x, y, s = 1, fill = 1, toppings = [1, 1, 1, 1], steam }) => {
  const [sauce = 0, cuke = 0, meat = 0, egg = 0] = toppings;
  const drop = (v: number) => (1 - v) * -260;
  return (
    <g transform={`translate(${x},${y}) scale(${s})`}>
      <ellipse cx={0} cy={150} rx={250} ry={30} fill="rgba(0,0,0,0.25)" />
      {/* bowl body */}
      <path d="M -300 0 Q -280 160 0 170 Q 280 160 300 0 Z" fill="#D8D4CF" />
      <path d="M -300 0 Q -280 160 0 170 Q 280 160 300 0 Z" fill="url(#bowlShade)" />
      <rect x={-300} y={40} width={600} height={10} fill="#3C5A88" opacity={0.85} />
      {/* rim + broth */}
      <ellipse cx={0} cy={0} rx={300} ry={80} fill="#EDEAE6" />
      <ellipse cx={0} cy={4} rx={270} ry={66} fill="#C99B5E" opacity={fill} />
      {/* noodles */}
      <g opacity={fill}>
        {Array.from({ length: 14 }).map((_, i) => (
          <path
            key={i}
            d={`M ${-220 + i * 30} ${20 - (i % 3) * 8} q 40 -50 80 -10 t 70 -20`}
            stroke="#F1E2B8"
            strokeWidth={9}
            fill="none"
            strokeLinecap="round"
          />
        ))}
      </g>
      {/* toppings */}
      <g transform={`translate(0,${drop(cuke)})`} opacity={cuke}>
        {[-60, -40, -20, 0, 20].map((dx, i) => (
          <rect key={i} x={dx - 70} y={-30 + i * 3} width={70} height={10} rx={5} fill="#6DA34D" transform={`rotate(${-20 + i * 8} ${dx - 35} -25)`} />
        ))}
      </g>
      <g transform={`translate(0,${drop(meat)})`} opacity={meat}>
        <ellipse cx={70} cy={-14} rx={70} ry={26} fill="#B97A5B" />
        <ellipse cx={70} cy={-18} rx={58} ry={18} fill="#D69A7A" />
      </g>
      <g transform={`translate(0,${drop(sauce)})`} opacity={sauce}>
        <path d="M -40 -20 Q -30 -70 10 -60 Q 50 -60 40 -20 Q 0 0 -40 -20 Z" fill="#C2311F" />
        <circle cx={-6} cy={-46} r={8} fill="#E0644E" />
      </g>
      <g transform={`translate(0,${drop(egg)})`} opacity={egg}>
        <ellipse cx={-10} cy={-70} rx={40} ry={30} fill="#FFFDF6" />
        <circle cx={-10} cy={-72} r={17} fill="#F4B63E" />
      </g>
      {steam !== undefined &&
        [0, 1, 2].map((k) => {
          const p = ((steam + k * 22) % 66) / 66;
          return (
            <path
              key={k}
              d={`M ${-80 + k * 80} ${-90 - p * 160} q 20 -30 0 -60 q -20 -30 0 -60`}
              stroke="#FFFFFF"
              strokeWidth={10}
              fill="none"
              strokeLinecap="round"
              opacity={0.5 * Math.sin(p * Math.PI)}
            />
          );
        })}
    </g>
  );
};

export const Defs: React.FC = () => (
  <defs>
    <linearGradient id="bowlShade" x1="0" x2="1">
      <stop offset="0" stopColor="#000" stopOpacity={0.18} />
      <stop offset="0.5" stopColor="#fff" stopOpacity={0.15} />
      <stop offset="1" stopColor="#000" stopOpacity={0.22} />
    </linearGradient>
    <clipPath id="zoomClip">
      <circle cx={0} cy={0} r={230} />
    </clipPath>
  </defs>
);

// ---------------------------------------------------------------- map pin
export const Pin: React.FC<{ x: number; y: number; s?: number; text: string }> = ({ x, y, s = 1, text }) => (
  <g transform={`translate(${x},${y}) scale(${s})`}>
    <path d="M 0 0 C -40 -50 -60 -80 -60 -110 A 60 60 0 1 1 60 -110 C 60 -80 40 -50 0 0 Z" fill="#D9442E" stroke="#1C1714" strokeWidth={6} />
    <circle cx={0} cy={-110} r={22} fill="#FFF4E2" />
    <g transform="translate(0,-210)">
      <rect x={-130} y={-50} width={260} height={84} rx={42} fill="#FFF4E2" stroke="#1C1714" strokeWidth={6} />
      <text x={0} y={12} textAnchor="middle" fontFamily="Pretendard" fontWeight={900} fontSize={50} fill="#1C1714">
        {text}
      </text>
    </g>
  </g>
);
