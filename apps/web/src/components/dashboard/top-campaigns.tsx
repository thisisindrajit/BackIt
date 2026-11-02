"use client";

import Link from "next/link";
import { ArrowRightIcon, FlameIcon } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { covers } from "@/components/backit/covers";
import { cn } from "@/lib/utils";
import type { ProductSummary } from "@/lib/api/types";

type Live = ProductSummary & { campaign: NonNullable<ProductSummary["campaign"]> };

function pitch(c: Live["campaign"]) {
  const left = c.spots_cap - c.spots_taken;
  const backers = `${c.backers} ${c.backers === 1 ? "backer" : "backers"}`;
  if (left > 0 && left <= 10) return `${backers} · only ${left} founding ${left === 1 ? "spot" : "spots"} left`;
  return `${backers} · ${c.spots_taken}/${c.spots_cap} founding spots`;
}

export function TopCampaigns({ products, limit = 3 }: { products?: ProductSummary[]; limit?: number }) {
  const live = products
    ?.filter((p): p is Live => p.campaign?.status === "published")
    .toSorted((a, b) => b.campaign.backers - a.campaign.backers || b.campaign.spots_taken - a.campaign.spots_taken)
    .slice(0, limit);

  return (
    <div className="flex h-full flex-col gap-4 rounded-3xl bg-secondary/45 p-4 ring-1 ring-foreground/[0.05] sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h3 className="flex items-center gap-2 font-heading text-xl">
            <FlameIcon className="size-4 text-primary" aria-hidden />
            Your top campaigns
          </h3>
          <p className="text-sm text-pretty text-foreground/70">Your live campaigns, ranked by backers.</p>
        </div>
        <Link
          href="/app/products"
          className="group/all flex shrink-0 items-center gap-1 rounded-full px-2 py-1 text-sm text-foreground/70 outline-none hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          Show all
          <ArrowRightIcon className="size-3.5 transition-transform duration-200 group-hover/all:translate-x-0.5" aria-hidden />
        </Link>
      </div>

      {!live ? (
        <ol className="flex flex-col gap-2" aria-hidden>
          {Array.from({ length: limit }, (_, i) => (
            <li key={i} className="flex items-center gap-3 rounded-2xl bg-card/70 p-3">
              <Skeleton className="size-11 shrink-0 rounded-xl" />
              <div className="flex flex-1 flex-col gap-1.5">
                <Skeleton className="h-4 w-28" />
                <Skeleton className="h-3 w-40 max-w-full" />
              </div>
            </li>
          ))}
        </ol>
      ) : live.length ? (
        <ol className="flex flex-col gap-2">
          {live.map((p, i) => (
            <li key={p.id}>
              <Link
                href={`/app/products/${p.id}`}
                className="lift group/top flex items-center gap-3 rounded-2xl bg-card p-3 outline-none ring-1 ring-foreground/[0.05] focus-visible:ring-3 focus-visible:ring-ring/50"
              >
                <span
                  aria-hidden
                  className={cn(
                    "relative flex size-11 shrink-0 items-end justify-center overflow-hidden rounded-xl font-display text-4xl leading-none text-foreground/80 italic",
                    covers[i % covers.length],
                  )}
                >
                  <span className="-mb-1.5 transition-transform duration-300 ease-(--ease-out) group-hover/top:-translate-y-0.5 group-hover/top:-rotate-3">
                    {p.name.slice(0, 1)}
                  </span>
                </span>
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="flex min-w-0 items-baseline gap-1.5">
                    <span className="tabular text-xs text-muted-foreground">#{i + 1}</span>
                    <span className="truncate font-medium">{p.name}</span>
                  </span>
                  <span className="truncate text-xs text-muted-foreground">{pitch(p.campaign)}</span>
                </span>
              </Link>
            </li>
          ))}
        </ol>
      ) : (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 py-6 text-center">
          <p className="text-sm text-muted-foreground">None of your campaigns are live yet.</p>
          <Link href="/app/products" className="text-sm text-link underline-offset-4 hover:underline">
            Publish one to start ranking
          </Link>
        </div>
      )}

      <p className="mt-auto text-xs text-pretty text-foreground/60">
        Campaigns climb when backers share. Every friend who buys earns the backer a reward.
      </p>
    </div>
  );
}
