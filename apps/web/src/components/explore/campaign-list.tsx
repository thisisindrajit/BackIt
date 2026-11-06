import Link from "next/link";
import { HandHeartIcon } from "lucide-react";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { covers } from "@/components/backit/covers";
import { money } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ExploreSort } from "@/lib/api/server";
import type { PublicCampaignCard } from "@/lib/api/types";

const sorts: { value: ExploreSort; label: string }[] = [
  { value: "trending", label: "Trending" },
  { value: "new", label: "Newest" },
];

export function parseSort(value: string | string[] | undefined): ExploreSort {
  return value === "new" ? "new" : "trending";
}

export function SortTabs({ basePath, current }: { basePath: string; current: ExploreSort }) {
  return (
    <nav aria-label="Sort campaigns" className="flex w-fit gap-1 rounded-full bg-muted p-1">
      {sorts.map((s) => (
        <Link
          key={s.value}
          href={s.value === "trending" ? basePath : `${basePath}?sort=${s.value}`}
          scroll={false}
          aria-current={s.value === current ? "page" : undefined}
          className="rounded-full px-4 py-1.5 text-sm text-foreground/70 transition-colors duration-150 outline-none hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50 aria-[current=page]:bg-background aria-[current=page]:text-foreground aria-[current=page]:shadow-sm"
        >
          {s.label}
        </Link>
      ))}
    </nav>
  );
}

function CampaignRow({ card: c, rank }: { card: PublicCampaignCard; rank: number }) {
  const { spots_cap: cap, spots_left: left } = c.founding;
  return (
    <li>
      <Link
        href={`/${c.slug}`}
        className="lift group/row flex items-center gap-4 rounded-3xl bg-card p-4 shadow-soft ring-1 ring-foreground/[0.07] outline-none focus-visible:ring-3 focus-visible:ring-ring/50 sm:gap-5 sm:p-5"
      >
        <span aria-hidden className="tabular hidden w-7 shrink-0 text-center font-display text-2xl text-muted-foreground italic sm:block">
          {rank}
        </span>
        <span
          aria-hidden
          className={cn(
            "flex size-14 shrink-0 items-end justify-center overflow-hidden rounded-2xl font-display text-5xl leading-none text-foreground/80 italic sm:size-16 sm:text-6xl",
            covers[(rank - 1) % covers.length],
          )}
        >
          <span className="-mb-2 transition-transform duration-300 ease-(--ease-out) group-hover/row:-translate-y-0.5 group-hover/row:-rotate-3">
            {c.product.name.slice(0, 1)}
          </span>
        </span>
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <p className="flex min-w-0 items-baseline gap-2">
            <span className="truncate font-heading text-lg">{c.product.name}</span>
            <span className="hidden truncate text-sm text-muted-foreground sm:inline">by {c.builder_name}</span>
          </p>
          <p className="line-clamp-2 text-[0.9375rem] text-foreground/75 sm:line-clamp-1">{c.headline}</p>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground">
            <span>
              <span className="tabular font-medium text-foreground">{money(c.founding.price_cents)}</span> · {c.offer.label}
            </span>
            <span className="flex items-center gap-2">
              <Progress value={((cap - left) / cap) * 100} aria-label="Founding spots taken" className="hidden w-16 gap-0 sm:flex" />
              <span className="tabular whitespace-nowrap">
                {left ? (
                  <>
                    {left}
                    <span className="hidden sm:inline"> of {cap}</span> spots left
                  </>
                ) : (
                  "Spots full"
                )}
              </span>
            </span>
            {c.commission_cents ? (
              <span className="hidden rounded-full bg-accent px-2.5 py-0.5 text-foreground/80 md:inline">
                Earn <span className="tabular">{money(c.commission_cents)}</span> per friend
              </span>
            ) : null}
          </div>
        </div>
        <span className="flex w-14 shrink-0 sm:w-16 flex-col items-center gap-0.5 rounded-2xl py-2.5 ring-1 ring-foreground/10 transition-colors duration-200 group-hover/row:bg-primary group-hover/row:text-white group-hover/row:ring-primary">
          <HandHeartIcon className="size-4" aria-hidden />
          <span className="tabular text-base font-medium">{c.backers}</span>
          <span className="sr-only">{c.backers === 1 ? "backer" : "backers"}</span>
        </span>
      </Link>
    </li>
  );
}

export function CampaignList({ campaigns }: { campaigns: PublicCampaignCard[] }) {
  if (!campaigns.length) {
    return (
      <Empty className="rounded-3xl bg-muted/60">
        <EmptyHeader>
          <EmptyTitle>No campaigns live yet</EmptyTitle>
          <EmptyDescription>When builders publish a founding-backer campaign, it shows up here.</EmptyDescription>
        </EmptyHeader>
      </Empty>
    );
  }
  return (
    <ol className="stagger flex flex-col gap-3">
      {campaigns.map((c, i) => (
        <CampaignRow key={c.slug} card={c} rank={i + 1} />
      ))}
    </ol>
  );
}

export function CampaignListSkeleton() {
  return (
    <div className="flex flex-col gap-3" aria-busy>
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="flex items-center gap-4 rounded-3xl p-4 ring-1 ring-foreground/[0.07] sm:gap-5 sm:p-5">
          <Skeleton className="hidden size-7 rounded-full sm:block" />
          <Skeleton className="size-14 rounded-2xl sm:size-16" />
          <div className="flex flex-1 flex-col gap-2">
            <Skeleton className="h-5 w-32 rounded-full" />
            <Skeleton className="h-4 w-3/5 rounded-full" />
            <Skeleton className="h-4 w-48 rounded-full" />
          </div>
          <Skeleton className="h-[4.5rem] w-16 rounded-2xl" />
        </div>
      ))}
    </div>
  );
}
