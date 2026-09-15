/**
 * Vetted SVG prop library. Each export renders a small, hand-drawn
 * illustration. The LLM cannot inject arbitrary SVG — it picks from
 * these kinds only.
 */
import React from "react";

import type { PropKind } from "../scenes/types";

const stroke = { fill: "none", stroke: "#FFFFFF", strokeWidth: 6, strokeLinecap: "round" as const };

const Snowflake: React.FC = () => (
  <g style={stroke} opacity={0.9}>
    <line x1={-40} y1={0} x2={40} y2={0} />
    <line x1={0} y1={-40} x2={0} y2={40} />
    <line x1={-30} y1={-30} x2={30} y2={30} />
    <line x1={-30} y1={30} x2={30} y2={-30} />
  </g>
);

const Fire: React.FC = () => (
  <g>
    <path d="M0 -50 C 30 -30, 40 0, 20 30 L -20 30 C -40 0, -30 -30, 0 -50 Z"
      fill="#FF6B35" stroke="#FFD166" strokeWidth={3} />
    <path d="M0 -20 C 15 -10, 20 5, 10 18 L -10 18 C -20 5, -15 -10, 0 -20 Z"
      fill="#FFD166" />
  </g>
);

const Cave: React.FC = () => (
  <g style={stroke}>
    <path d="M -120 80 Q -100 -120, 0 -120 Q 100 -120, 120 80 Z" fill="#3D3D5C" />
    <ellipse cx={0} cy={30} rx={50} ry={20} fill="#FFD166" opacity={0.6} />
  </g>
);

const HumanSilhouette: React.FC = () => (
  <g style={{ ...stroke, fill: "#FFD166" }}>
    <circle cx={0} cy={-90} r={28} />
    <rect x={-30} y={-60} width={60} height={100} rx={20} />
  </g>
);

const Timeline: React.FC = () => (
  <g style={stroke}>
    <line x1={-200} y1={0} x2={200} y2={0} />
    {[-200, -100, 0, 100, 200].map((x) => (
      <line key={x} x1={x} y1={-10} x2={x} y2={10} />
    ))}
    <circle cx={-100} cy={0} r={10} fill="#FF6B35" />
    <circle cx={0} cy={0} r={10} fill="#FFD166" />
  </g>
);

const Mountain: React.FC = () => (
  <g style={stroke} fill="#5A6B7B">
    <path d="M -120 60 L -40 -80 L 20 0 L 60 -60 L 120 60 Z" />
  </g>
);

const Mammoth: React.FC = () => (
  <g style={{ fill: "#3D3D5C", stroke: "#FFFFFF", strokeWidth: 4 }}>
    <ellipse cx={0} cy={0} rx={80} ry={50} />
    <circle cx={70} cy={-30} r={25} />
    <path d="M 90 -20 Q 110 -10, 105 10" fill="none" />
    <path d="M 95 0 Q 115 5, 115 25" fill="none" />
    <line x1={-60} y1={50} x2={-60} y2={90} stroke="#FFFFFF" strokeWidth={6} />
    <line x1={-30} y1={50} x2={-30} y2={90} stroke="#FFFFFF" strokeWidth={6} />
    <line x1={0} y1={50} x2={0} y2={90} stroke="#FFFFFF" strokeWidth={6} />
    <line x1={30} y1={50} x2={30} y2={90} stroke="#FFFFFF" strokeWidth={6} />
  </g>
);

const Arrow: React.FC = () => (
  <g style={stroke}>
    <line x1={-50} y1={0} x2={50} y2={0} />
    <polyline points="30,-15 50,0 30,15" />
  </g>
);

const ChartAxes: React.FC = () => (
  <g style={stroke}>
    <line x1={-100} y1={80} x2={100} y2={80} />
    <line x1={-100} y1={80} x2={-100} y2={-80} />
  </g>
);

const TreePine: React.FC = () => (
  <g style={{ fill: "#2D5A3D", stroke: "#FFFFFF", strokeWidth: 4 }}>
    <polygon points="0,-100 -40,-20 40,-20" />
    <polygon points="0,-60 -30,10 30,10" />
    <rect x={-8} y={10} width={16} height={30} fill="#5D4037" />
  </g>
);

const Sun: React.FC = () => (
  <g>
    <circle cx={0} cy={0} r={40} fill="#FFD166" />
    {[0, 45, 90, 135, 180, 225, 270, 315].map((deg) => (
      <line key={deg}
        x1={0} y1={-60} x2={0} y2={-80}
        stroke="#FFD166" strokeWidth={6}
        transform={`rotate(${deg})`} />
    ))}
  </g>
);

const QuestionMark: React.FC = () => (
  <g style={{ ...stroke, fill: "none" }}>
    <path d="M -25 -20 C -25 -50, 25 -50, 25 -20 C 25 0, 0 0, 0 20" strokeWidth={10} />
    <circle cx={0} cy={40} r={6} fill="#FFFFFF" />
  </g>
);

const REGISTRY: Record<PropKind, React.FC> = {
  human_silhouette: HumanSilhouette,
  cave: Cave,
  fire: Fire,
  tree_pine: TreePine,
  snowflake: Snowflake,
  arrow: Arrow,
  timeline: Timeline,
  chart_axes: ChartAxes,
  animal_mammoth: Mammoth,
  sun: Sun,
  mountain: Mountain,
  question_mark: QuestionMark,
};

interface Props {
  kind: PropKind;
}

export const PropRenderer: React.FC<Props> = ({ kind }) => {
  const Component = REGISTRY[kind] ?? QuestionMark;
  return <Component />;
};
