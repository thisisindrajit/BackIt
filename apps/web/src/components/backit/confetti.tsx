"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/utils";

const COLORS = ["var(--primary)", "var(--secondary)", "#e6d77a", "var(--primary-deep)", "#f3e7a6", "#a9c0a6"];
const SHAPES = ["h-3.5 w-2 rounded-[2px]", "size-2 rounded-full", "h-4 w-1 rounded-full", "size-2.5 rounded-[2px]"];

// Seeded so every burst looks the same and stays cheap to compute.
function rand(seed: number) {
  const x = Math.sin(seed * 9301 + 49297) * 233280;
  return x - Math.floor(x);
}

type Piece = { side: "left" | "right"; dx: number; peak: number; fall: number; r: number; dur: number; delay: number; color: string; shape: string; flutter: number };

const PIECES: Piece[] = Array.from({ length: 140 }, (_, i) => {
  const side = i % 2 === 0 ? "left" : "right";
  const wave = i < 96 ? 0 : 1;
  const a = rand(i + 1);
  const b = rand(i + 101);
  const c = rand(i + 211);
  const dx = 18 + a * 52;
  return {
    side,
    dx: side === "left" ? dx : -dx,
    peak: -(52 + b * 40),
    fall: 8 + c * 20,
    r: Math.round((a - 0.5) * 1440),
    dur: 2300 + Math.round(c * 1100),
    delay: wave * 380 + Math.round(b * 160),
    color: COLORS[i % COLORS.length],
    shape: SHAPES[i % SHAPES.length],
    flutter: 380 + Math.round(a * 520),
  };
});

const KEY = "backit:celebrated:";

/**
 * Full-screen confetti from both bottom corners, fired once per `id` (remembered in localStorage).
 * Mount it only on the client after data loads. Renders nothing under reduced motion.
 */
export function Confetti({ id }: { id: string }) {
  const [show, setShow] = useState(() => {
    if (typeof window === "undefined") return false;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return false;
    try {
      return !window.localStorage.getItem(KEY + id);
    } catch {
      return true;
    }
  });

  useEffect(() => {
    if (!show) return;
    try {
      window.localStorage.setItem(KEY + id, "1");
    } catch {}
    const t = setTimeout(() => setShow(false), 4200);
    return () => clearTimeout(t);
  }, [show, id]);

  if (!show) return null;
  return createPortal(
    <div aria-hidden className="pointer-events-none fixed inset-0 z-50 overflow-hidden">
      {PIECES.map((p, i) => (
        <span
          key={i}
          className={cn("confetti-piece absolute bottom-0", p.side === "left" ? "left-0" : "right-0")}
          style={
            {
              "--dx": `${p.dx}vw`,
              "--peak": `${p.peak}vh`,
              "--fall": `${p.fall}vh`,
              "--r": `${p.r}deg`,
              animation: `confetti ${p.dur}ms linear ${p.delay}ms both`,
            } as React.CSSProperties
          }
        >
          <span className={cn("confetti-flutter block", p.shape)} style={{ background: p.color, animationDuration: `${p.flutter}ms` }} />
        </span>
      ))}
    </div>,
    document.body,
  );
}
