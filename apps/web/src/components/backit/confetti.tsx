import { cn } from "@/lib/utils";

const colors = ["var(--primary)", "var(--secondary)", "#e6d77a", "var(--primary-deep)", "var(--accent)"];

// Deterministic burst so server and client render the same pieces.
const pieces = Array.from({ length: 28 }, (_, i) => {
  const angle = (i / 28) * Math.PI * 2 + (i % 3) * 0.17;
  const dist = 90 + ((i * 37) % 70);
  return {
    dx: Math.round(Math.cos(angle) * dist),
    dy: Math.round(Math.sin(angle) * dist * 0.8 + 40),
    r: ((i * 53) % 540) - 270,
    color: colors[i % colors.length],
    round: i % 4 === 0,
    delay: (i % 5) * 20,
  };
});

/** One-time celebration burst (rare moment: a completed founding purchase). Hidden under reduced motion. */
export function Confetti({ className }: { className?: string }) {
  return (
    <div aria-hidden className={cn("pointer-events-none absolute inset-0 grid place-items-center", className)}>
      {pieces.map((p, i) => (
        <span
          key={i}
          className={cn("confetti-piece absolute h-2.5 w-1.5 opacity-0", p.round ? "size-2 rounded-full" : "rounded-[1px]")}
          style={
            {
              background: p.color,
              "--dx": `${p.dx}px`,
              "--dy": `${p.dy}px`,
              "--r": `${p.r}deg`,
              animation: `confetti 1100ms var(--ease-out) ${300 + p.delay}ms both`,
            } as React.CSSProperties
          }
        />
      ))}
    </div>
  );
}
