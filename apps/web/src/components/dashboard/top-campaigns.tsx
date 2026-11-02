"use client";

import Link from "next/link";
import { ArrowRightIcon, FlameIcon } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { covers } from "@/components/backit/covers";
import { useApi } from "@/hooks/use-api";
import { money } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { PublicCampaignCard } from "@/lib/api/types";

function pitch(c: PublicCampaignCard) {
  if (c.backers_this_week) return `${c.backers_this_week} backed this week`;
  if (c.founding.spots_left && c.founding.spots_left <= 10) return `Only ${c.founding.spots_left} founding spots left`;
  return `${c.backers} ${c.backers === 1 ? "backer" : "backers"} so far`;
}

export function TopCampaigns({ limit = 3, mine }: { limit?: number; mine: Set<string> }) {
  const { data, error } = useApi<PublicCampaignCard[]>("/public/campaigns?sort=trending");

  return (
    <div className="flex h-full flex-col gap-4 rounded-3xl bg-secondary/45 p-4 ring-1 ring-foreground/[0.05] sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h3 className="flex items-center gap-2 font-heading text-xl">
            <FlameIcon className="size-4 text-primary" aria-hidden />
            Top campaigns
          </h3>
          <p className="text-sm text-pretty text-foreground/70">What’s working for builders right now.</p>
        </div>
        <Link
          href="/app/explore"
          className="group/all flex shrink-0 items-center gap-1 rounded-full px-2 py-1 text-sm text-foreground/70 outline-none hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          All
          <ArrowRightIcon className="size-3.5 transition-transform duration-200 group-hover/all:translate-x-0.5" aria-hidden />
        </Link>
      </div>

      {error ? (
        <p className="py-6 text-center text-sm text-muted-foreground">Couldn’t load campaigns right now.</p>
      ) : !data ? (
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
      ) : data.length ? (
        <ol className="flex flex-col gap-2">
          {data.slice(0, limit).map((c, i) => (
            <li key={c.slug}>
              <Link
                href={`/${c.slug}`}
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
                    {c.product.name.slice(0, 1)}
                  </span>
                </span>
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="flex min-w-0 items-baseline gap-1.5">
                    <span className="tabular text-xs text-muted-foreground">#{i + 1}</span>
                    <span className="truncate font-medium">{c.product.name}</span>
                    {mine.has(c.slug) ? (
                      <span className="shrink-0 rounded-full bg-primary px-1.5 py-px text-[0.6875rem] text-white">Yours</span>
                    ) : null}
                  </span>
                  <span className="truncate text-xs text-muted-foreground">
                    by {c.builder_name} · {pitch(c)}
                  </span>
                </span>
                {c.commission_cents ? (
                  <span className="tabular hidden shrink-0 rounded-full bg-accent px-2 py-0.5 text-xs text-accent-foreground min-[400px]:inline">
                    {money(c.commission_cents)}/friend
                  </span>
                ) : null}
              </Link>
            </li>
          ))}
        </ol>
      ) : (
        <p className="py-6 text-center text-sm text-muted-foreground">No live campaigns yet. Yours could be the first.</p>
      )}

      <p className="mt-auto text-xs text-pretty text-foreground/60">
        Campaigns climb when backers share. Every friend who buys earns the backer a reward.
      </p>
    </div>
  );
}
