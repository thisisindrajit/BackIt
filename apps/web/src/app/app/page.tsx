"use client";

import Link from "next/link";
import { ArrowRightIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/backit/error-state";
import { FoundingSeal } from "@/components/backit/founding-seal";
import { PageHeader } from "@/components/backit/page-header";
import { NewProductTile, ProductTile } from "@/components/backit/product-tile";
import { useApi } from "@/hooks/use-api";
import type { Me } from "@/lib/api/types";

export default function OverviewPage() {
  const { data, error, loading, reload } = useApi<Me>("/me");

  if (error) return <ErrorState error={error} onRetry={reload} />;
  const first = data?.profile.display_name.split(" ")[0];

  return (
    <>
      <PageHeader
        title={
          first ? (
            <>
              Good to see you, <em>{first}.</em>
            </>
          ) : (
            "Home"
          )
        }
        description="Run your own campaign, or keep track of the builders you back."
      />

      <section className="flex flex-col gap-5">
        <div className="flex items-end justify-between gap-4">
          <h2 className="text-2xl">Your campaigns</h2>
          {data?.products.length ? (
            <Button render={<Link href="/app/products" />} nativeButton={false} variant="ghost" size="sm">
              All campaigns
              <ArrowRightIcon data-icon="inline-end" />
            </Button>
          ) : null}
        </div>
        {loading && !data ? (
          <Skeleton className="h-56 rounded-3xl" />
        ) : (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {data?.products.slice(0, 5).map((p, i) => <ProductTile key={p.id} product={p} index={i} />)}
            <NewProductTile />
          </div>
        )}
      </section>

      <section className="flex flex-col gap-5">
        <div className="flex items-end justify-between gap-4">
          <h2 className="text-2xl">Builders you back</h2>
          {data?.backings.length ? (
            <Button render={<Link href="/app/backings" />} nativeButton={false} variant="ghost" size="sm">
              Share and earnings
              <ArrowRightIcon data-icon="inline-end" />
            </Button>
          ) : null}
        </div>
        {loading && !data ? (
          <Skeleton className="h-24 rounded-3xl" />
        ) : data?.backings.length ? (
          <div className="grid gap-3 sm:grid-cols-2">
            {data.backings.map((b) => (
              <Link
                key={b.id}
                href="/app/backings"
                className="lift flex items-center gap-4 rounded-3xl bg-card p-4 shadow-soft ring-1 ring-foreground/[0.07] outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
              >
                <FoundingSeal number={b.badge_number ?? undefined} size={64} />
                <span className="flex min-w-0 flex-col">
                  <span className="truncate font-heading text-lg">{b.campaign_headline}</span>
                  <span className="text-sm text-muted-foreground">{b.badge_number ? `Founding backer #${b.badge_number}` : "Referred customer"}</span>
                </span>
              </Link>
            ))}
          </div>
        ) : (
          <Empty className="rounded-3xl bg-muted/60">
            <EmptyHeader>
              <EmptyTitle>You haven’t backed anyone yet</EmptyTitle>
              <EmptyDescription>When a builder shares their campaign link with you, buy a founding spot to get your own referral link.</EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}
      </section>
    </>
  );
}
