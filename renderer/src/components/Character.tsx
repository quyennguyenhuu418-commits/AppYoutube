/**
 * Stick-figure character renderer.
 *
 * Pure SVG. Poses are mapped to a small set of pre-baked paths so the
 * LLM cannot inject arbitrary SVG. This keeps every character visually
 * consistent across videos.
 */
import React from "react";

import type { Pose } from "../scenes/types";

interface Props {
  color: string;
  pose: Pose;
  size?: number;
}

const STROKE = 6;

const HEAD = (
  <circle cx="0" cy={-60} r={20} fill="none" stroke="currentColor" strokeWidth={STROKE} />
);

const TORSO = (
  <line x1="0" y1={-40} x2="0" y2={20} stroke="currentColor" strokeWidth={STROKE} />
);

const LEGS_BASE = (
  <>
    <line x1="0" y1={20} x2={-20} y2={60} stroke="currentColor" strokeWidth={STROKE} />
    <line x1="0" y1={20} x2={20} y2={60} stroke="currentColor" strokeWidth={STROKE} />
  </>
);

const LEGS_SITTING = (
  <>
    <line x1="0" y1={20} x2={-25} y2={35} stroke="currentColor" strokeWidth={STROKE} />
    <line x1="0" y1={20} x2={25} y2={35} stroke="currentColor" strokeWidth={STROKE} />
    <line x1={-25} y1={35} x2={-25} y2={60} stroke="currentColor" strokeWidth={STROKE} />
    <line x1={25} y1={35} x2={25} y2={60} stroke="currentColor" strokeWidth={STROKE} />
  </>
);

const LEGS_RUNNING = (
  <>
    <line x1="0" y1={20} x2={-30} y2={45} stroke="currentColor" strokeWidth={STROKE} />
    <line x1="0" y1={20} x2={30} y2={50} stroke="currentColor" strokeWidth={STROKE} />
  </>
);

const ARMS_DOWN = (
  <>
    <line x1="0" y1={-25} x2={-25} y2={5} stroke="currentColor" strokeWidth={STROKE} />
    <line x1="0" y1={-25} x2={25} y2={5} stroke="currentColor" strokeWidth={STROKE} />
  </>
);

const ARMS_POINT_RIGHT = (
  <>
    <line x1="0" y1={-25} x2={-25} y2={5} stroke="currentColor" strokeWidth={STROKE} />
    <line x1="0" y1={-25} x2={45} y2={-30} stroke="currentColor" strokeWidth={STROKE} />
  </>
);

const ARMS_POINT_UP = (
  <>
    <line x1="0" y1={-25} x2={-25} y2={-50} stroke="currentColor" strokeWidth={STROKE} />
    <line x1="0" y1={-25} x2={25} y2={-50} stroke="currentColor" strokeWidth={STROKE} />
  </>
);

const ARMS_HIDE = (
  <>
    <line x1="0" y1={-25} x2={-30} y2={20} stroke="currentColor" strokeWidth={STROKE} />
    <line x1="0" y1={-25} x2={30} y2={20} stroke="currentColor" strokeWidth={STROKE} />
  </>
);

const ARMS_CELEBRATE = (
  <>
    <line x1="0" y1={-25} x2={-30} y2={-70} stroke="currentColor" strokeWidth={STROKE} />
    <line x1="0" y1={-25} x2={30} y2={-70} stroke="currentColor" strokeWidth={STROKE} />
  </>
);

const ARMS_THINK = (
  <>
    <line x1="0" y1={-25} x2={-25} y2={5} stroke="currentColor" strokeWidth={STROKE} />
    <line x1="0" y1={-25} x2={20} y2={-55} stroke="currentColor" strokeWidth={STROKE} />
  </>
);

const POSE_ARMS: Record<Pose, React.ReactNode> = {
  stand: ARMS_DOWN,
  walk: ARMS_DOWN,
  run: ARMS_POINT_RIGHT,
  sit: ARMS_DOWN,
  point: ARMS_POINT_RIGHT,
  think: ARMS_THINK,
  celebrate: ARMS_CELEBRATE,
  hide: ARMS_HIDE,
};

const POSE_LEGS: Record<Pose, React.ReactNode> = {
  stand: LEGS_BASE,
  walk: LEGS_BASE,
  run: LEGS_RUNNING,
  sit: LEGS_SITTING,
  point: LEGS_BASE,
  think: LEGS_BASE,
  celebrate: LEGS_BASE,
  hide: LEGS_BASE,
};

export const Character: React.FC<Props> = ({ color, pose, size = 1 }) => {
  return (
    <g
      style={{ color }}
      transform={`scale(${size})`}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {HEAD}
      {TORSO}
      {POSE_ARMS[pose]}
      {POSE_LEGS[pose]}
    </g>
  );
};
