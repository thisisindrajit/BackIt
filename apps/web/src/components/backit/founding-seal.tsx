import { useId } from "react";
import { cn } from "@/lib/utils";

const RING = "FOUNDING BACKER  •  BACKIT.CLUB  •  FOUNDING BACKER  •  BACKIT.CLUB  •  ";

/** The numbered founding-backer seal. `spin` slowly turns the ring text (decorative, marketing only). */
export function FoundingSeal({
  number,
  size = 120,
  spin = false,
  className,
}: {
  number?: number | string;
  size?: number;
  spin?: boolean;
  className?: string;
}) {
  const id = useId();
  const label = number ? `Founding backer badge number ${number}` : "Founding backer badge";
  return (
    <svg
      role="img"
      aria-label={label}
      viewBox="0 0 200 200"
      width={size}
      height={size}
      className={cn("shrink-0 drop-shadow-[0_10px_18px_rgb(27_35_28/0.16)]", className)}
    >
      <defs>
        <path id={`${id}-ring`} d="M100,100 m-78,0 a78,78 0 1,1 156,0 a78,78 0 1,1 -156,0" />
      </defs>
      <circle cx="100" cy="100" r="98" fill="var(--secondary)" />
      <circle cx="100" cy="100" r="92" fill="none" stroke="var(--primary-deep)" strokeOpacity="0.35" strokeWidth="1" />
      <circle cx="100" cy="100" r="62" fill="var(--accent)" stroke="var(--primary-deep)" strokeOpacity="0.5" strokeWidth="1" strokeDasharray="2 4" />
      <g className={spin ? "spin-slow" : undefined} style={{ transformOrigin: "100px 100px" }}>
        <text fill="var(--primary-deep)" fontSize="12.5" fontWeight="600" letterSpacing="2.2" fontFamily="var(--font-sans)">
          <textPath href={`#${id}-ring`} textLength="486" lengthAdjust="spacing">
            {RING}
          </textPath>
        </text>
      </g>
      <text x="100" y="82" textAnchor="middle" fill="var(--primary-deep)" fontSize="13" fontWeight="600" letterSpacing="1.5" fontFamily="var(--font-sans)">
        NO.
      </text>
      <text
        x="100"
        y="130"
        textAnchor="middle"
        fill="var(--foreground)"
        fontSize={String(number ?? "").length > 2 ? 40 : 52}
        fontStyle="italic"
        fontFamily="var(--font-serif)"
        style={{ fontVariantNumeric: "lining-nums" }}
      >
        {number ?? "★"}
      </text>
    </svg>
  );
}
