"use client";

import Link from "next/link";
import { PlusIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Progress } from "@/components/ui/progress";
import { StatusBadge } from "@/components/backit/status-badge";
import { usePrefetch } from "@/hooks/use-api";
import { cn } from "@/lib/utils";
import type { Me } from "@/lib/api/types";
import { covers } from "./covers";

export function ProductTile({ product: p, index }: { product: Me["products"][number]; index: number }) {
  const prefetch = usePrefetch();
  const c = p.campaign;
  return (
    <Link
      href={`/app/products/${p.id}`}
      onPointerEnter={() => prefetch(`/products/${p.id}`)}
      onFocus={() => prefetch(`/products/${p.id}`)}
      className="lift group/tile flex flex-col overflow-hidden rounded-3xl bg-card shadow-soft ring-1 ring-foreground/[0.07] outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
    >
      <div className={cn("relative flex h-28 items-end justify-between overflow-hidden px-5 pb-3", covers[index % covers.length])}>
        <span
          aria-hidden
          className="font-display -mb-5 text-[6rem] leading-none text-foreground/80 italic transition-transform duration-300 ease-(--ease-out) group-hover/tile:-translate-y-1 group-hover/tile:-rotate-3"
        >
          {p.name.slice(0, 1)}
        </span>
        <StatusBadge status={p.campaign?.status ?? "draft"} className="mb-1 bg-background/90" />
      </div>
      <div className="flex flex-1 flex-col gap-4 px-5 pt-4 pb-5">
        <div className="flex flex-col gap-1">
          <span className="truncate font-heading text-lg">{p.name}</span>
          <span className="line-clamp-1 text-sm text-muted-foreground">{c?.headline || p.description}</span>
        </div>
        {c ? (
          <div className="mt-auto flex flex-col gap-2">
            <Progress
              value={c.spots_cap ? (c.spots_taken / c.spots_cap) * 100 : 0}
              aria-label="Founding spots taken"
              className="gap-0"
            />
            <span className="tabular text-sm text-muted-foreground">
              {c.spots_taken} of {c.spots_cap} spots · {c.backers} {c.backers === 1 ? "backer" : "backers"}
            </span>
          </div>
        ) : (
          <span className="mt-auto text-sm text-muted-foreground">No campaign yet</span>
        )}
      </div>
    </Link>
  );
}

/** Desktop users already have "New campaign" in the sidebar, so the button only shows where the sidebar is hidden. */
export function NoCampaigns() {
  return (
    <Empty className="rounded-3xl bg-muted/60">
      <EmptyHeader>
        <EmptyTitle>No campaigns yet</EmptyTitle>
        <EmptyDescription>
          Add your product and we’ll help you draft a founding-backer offer. <span className="max-md:hidden">Start with New campaign in the sidebar.</span>
        </EmptyDescription>
      </EmptyHeader>
      <EmptyContent className="md:hidden">
        <Button render={<Link href="/app/products/new" />} nativeButton={false}>
          <PlusIcon data-icon="inline-start" />
          New campaign
        </Button>
      </EmptyContent>
    </Empty>
  );
}
