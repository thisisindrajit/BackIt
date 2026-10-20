import { FoundingSeal } from "@/components/backit/founding-seal";
import { Wordmark } from "@/components/backit/wordmark";

const chips = [
  { text: "Priya became backer #2", dot: "bg-primary", pos: "top-[6%] left-[2%]", tilt: "-4deg", delay: "0s" },
  { text: "+$20 reward for Sam", dot: "bg-[#e6c94c]", pos: "top-[16%] right-[0%]", tilt: "3deg", delay: "-1.6s" },
  { text: "Jon’s friend joined", dot: "bg-primary", pos: "bottom-[14%] left-[0%]", tilt: "3deg", delay: "-3.1s" },
  { text: "Paid out via PayPal", dot: "bg-primary-deep", pos: "bottom-[4%] right-[4%]", tilt: "-3deg", delay: "-2.3s" },
];

export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <main className="grid min-h-svh lg:grid-cols-[1fr_1.05fr]">
      <div className="flex flex-col px-5 py-6 sm:px-10">
        <Wordmark />
        <div className="rise mx-auto flex w-full max-w-sm flex-1 flex-col justify-center py-12">{children}</div>
      </div>
      <aside className="relative m-3 hidden flex-col items-center justify-center gap-[clamp(1.5rem,4svh,3rem)] overflow-hidden rounded-[2rem] bg-secondary/55 p-10 text-center lg:flex">
        <div aria-hidden className="pointer-events-none absolute -top-24 -left-24 size-80 rounded-full bg-accent/70 blur-3xl" />
        <div aria-hidden className="pointer-events-none absolute -right-20 -bottom-28 size-96 rounded-full bg-primary/25 blur-3xl" />

        <div aria-hidden className="relative h-[clamp(15rem,42svh,22rem)] w-full max-w-[30rem]">
          <div className="pop-in absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 [animation-delay:150ms]">
            <FoundingSeal number={1} size={200} spin />
          </div>
          <div className="pop-in absolute top-[30%] left-[10%] [animation-delay:450ms]">
            <div className="float [--tilt:-10deg] [animation-delay:-1s]">
              <FoundingSeal number={2} size={84} />
            </div>
          </div>
          <div className="pop-in absolute right-[10%] bottom-[30%] [animation-delay:600ms]">
            <div className="float [--tilt:8deg] [animation-delay:-2.5s]">
              <FoundingSeal number={3} size={68} />
            </div>
          </div>
          {chips.map((c, i) => (
            <div key={c.text} className={`rise absolute ${c.pos}`} style={{ animationDelay: `${700 + i * 120}ms` }}>
              <div
                className="float flex items-center gap-2 rounded-full bg-card px-3.5 py-2 text-sm whitespace-nowrap shadow-lift ring-1 ring-foreground/[0.06]"
                style={{ "--tilt": c.tilt, animationDelay: c.delay } as React.CSSProperties}
              >
                <span className={`size-2 rounded-full ${c.dot}`} />
                {c.text}
              </div>
            </div>
          ))}
        </div>

        <div className="relative flex flex-col items-center gap-4">
          <p className="max-w-md font-display text-[clamp(2rem,4.5svh,2.5rem)] leading-[1.05] tracking-[-0.02em] text-balance">
            The people who believed early become <em>the reason others sign up.</em>
          </p>
          <p className="max-w-sm text-sm text-foreground/70">Backers earn from purchases and referrals only. No equity, no investment returns.</p>
        </div>
      </aside>
    </main>
  );
}
