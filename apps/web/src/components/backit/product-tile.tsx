import Link from "next/link";
import { PlusIcon } from "lucide-react";
import { StatusBadge } from "@/components/backit/status-badge";
import { cn } from "@/lib/utils";
import type { Me } from "@/lib/api/types";

const covers = ["bg-secondary/70", "bg-accent", "bg-[#dfe8da]", "bg-muted"];

export function ProductTile({ product: p, index }: { product: Me["products"][number]; index: number }) {
  return (
    <Link
      href={`/app/products/${p.id}`}
      className="lift group/tile flex flex-col overflow-hidden rounded-3xl bg-card shadow-soft ring-1 ring-foreground/[0.07] outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
    >
      <div className={cn("relative flex h-36 items-end justify-between overflow-hidden px-5 pb-3", covers[index % covers.length])}>
        <span
          aria-hidden
          className="font-display -mb-6 text-[7rem] leading-none text-foreground/80 italic transition-transform duration-300 ease-(--ease-out) group-hover/tile:-translate-y-1 group-hover/tile:-rotate-3"
        >
          {p.name.slice(0, 1)}
        </span>
        <StatusBadge status={p.campaign?.status ?? "draft"} className="mb-1 bg-background/90" />
      </div>
      <div className="flex flex-col gap-0.5 px-5 py-4">
        <span className="font-heading text-lg">{p.name}</span>
        <span className="truncate text-sm text-muted-foreground">{p.campaign ? `backit.club/${p.campaign.slug}` : "No campaign yet"}</span>
      </div>
    </Link>
  );
}

export function NewProductTile() {
  return (
    <Link
      href="/app/products/new"
      className="lift group/new flex min-h-[13.5rem] flex-col items-center justify-center gap-3 rounded-3xl border border-dashed border-foreground/15 text-muted-foreground outline-none hover:border-primary hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
    >
      <span className="grid size-11 place-items-center rounded-full bg-muted transition-[transform,background-color] duration-200 ease-(--ease-out) group-hover/new:rotate-90 group-hover/new:bg-primary group-hover/new:text-white">
        <PlusIcon className="size-5" />
      </span>
      <span className="text-sm font-medium">Add a product</span>
    </Link>
  );
}
