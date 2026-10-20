import { cn } from "@/lib/utils";

// Synthetic sample entries for the landing demonstration.
const entries = [
  { what: "Priya became backer #14", who: "Bought early at the founding price", amount: "$60", tone: "in" },
  { what: "Sam’s friend joined", who: "Bought with Sam’s link", amount: "$80", tone: "in" },
  { what: "Sam earned a reward", who: "For bringing a friend", amount: "$20", tone: "held" },
  { what: "Jon became backer #15", who: "Bought early at the founding price", amount: "$60", tone: "in" },
  { what: "Maya paid Sam", who: "Sent through PayPal", amount: "$20", tone: "paid" },
] as const;

const toneDot: Record<(typeof entries)[number]["tone"], string> = {
  in: "bg-primary",
  held: "bg-[#e6d77a]",
  paid: "bg-primary-deep",
};

function Rows({ hidden }: { hidden?: boolean }) {
  return (
    <ul aria-hidden={hidden} className="flex flex-col">
      {entries.map((e, i) => (
        <li key={i} className="flex items-center gap-3 border-b border-foreground/[0.06] py-3.5">
          <span className={cn("size-2 shrink-0 rounded-full", toneDot[e.tone])} />
          <span className="flex min-w-0 flex-1 flex-col">
            <span className="truncate text-sm font-medium">{e.what}</span>
            <span className="truncate text-xs text-muted-foreground">{e.who}</span>
          </span>
          <span className="tabular font-heading text-base">{e.amount}</span>
        </li>
      ))}
    </ul>
  );
}

export function LedgerTicker() {
  return (
    <div className="ticker-pause flex h-[22rem] flex-col rounded-3xl bg-card p-5 shadow-lift ring-1 ring-foreground/[0.06]">
      <div className="flex items-center justify-between pb-2">
        <p className="font-heading text-lg">Recent activity</p>
        <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">Sample data</span>
      </div>
      <div className="relative flex-1 overflow-hidden [mask-image:linear-gradient(to_bottom,transparent,black_12%,black_88%,transparent)]">
        <div className="ticker">
          <Rows />
          <Rows hidden />
        </div>
      </div>
    </div>
  );
}
