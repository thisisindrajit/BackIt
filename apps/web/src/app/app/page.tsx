"use client";

import { useMemo } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { ErrorState } from "@/components/backit/error-state";
import { FoundingSeal } from "@/components/backit/founding-seal";
import { PageHeader } from "@/components/backit/page-header";
import { NoCampaigns, ProductTile } from "@/components/backit/product-tile";
import { PageHeaderSkeleton, RowCardSkeleton, TileGridSkeleton, tileGrid } from "@/components/backit/skeletons";
import { Skeleton } from "@/components/ui/skeleton";
import { TopCampaigns } from "@/components/dashboard/top-campaigns";
import { useApi, usePrefetch } from "@/hooks/use-api";
import { money, shortDate } from "@/lib/format";
import type { Activity, Me } from "@/lib/api/types";

const EarningsChart = dynamic(() => import("@/components/dashboard/earnings-chart").then((m) => m.EarningsChart), {
  ssr: false,
  loading: () => <ChartSkeleton />,
});

const pulseGrid = "grid gap-5 xl:grid-cols-[minmax(0,2fr)_minmax(20rem,1fr)]";
const noSlugs = new Set<string>();

function ChartSkeleton() {
  return (
    <div className="flex flex-col overflow-hidden rounded-3xl ring-1 ring-foreground/[0.07]" aria-hidden>
      <div className="grid grid-cols-3 border-b border-foreground/[0.07]">
        {[0, 1, 2].map((i) => (
          <div key={i} className="flex flex-col gap-2 px-3 py-4 sm:px-6 sm:py-5">
            <Skeleton className="h-3.5 w-16 sm:w-24" />
            <Skeleton className="h-6 w-20 sm:h-8 sm:w-28" />
          </div>
        ))}
      </div>
      <div className="flex flex-col gap-4 p-4 sm:p-6">
        <Skeleton className="h-4 w-56 max-w-full" />
        <Skeleton className="h-48 w-full rounded-2xl sm:h-56" />
      </div>
    </div>
  );
}

function Pulse({ mine }: { mine: Set<string> }) {
  const { data: activity, error, reload } = useApi<Activity>("/me/activity");
  return (
    <div className={pulseGrid}>
      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : activity ? (
        <EarningsChart activity={activity} />
      ) : (
        <ChartSkeleton />
      )}
      <TopCampaigns mine={mine} />
    </div>
  );
}

export default function OverviewPage() {
  const { data, error, reload } = useApi<Me>("/me");
  const prefetch = usePrefetch();
  const mine = useMemo(
    () => new Set(data?.products.flatMap((p) => (p.campaign ? [p.campaign.slug] : [])) ?? []),
    [data],
  );

  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (!data) {
    return (
      <>
        <PageHeaderSkeleton />
        <Pulse mine={noSlugs} />
        <Section title="Your campaigns">
          <TileGridSkeleton />
        </Section>
        <Section title="Builders you back">
          <RowCardSkeleton />
        </Section>
      </>
    );
  }

  const first = data.profile.display_name.split(" ")[0];

  return (
    <>
      <PageHeader
        title={
          <>
            Good to see you, <em>{first}.</em>
          </>
        }
        description="Run your own campaign, or keep track of the builders you back."
      />

      <Pulse mine={mine} />

      <Section title="Your campaigns">
        {data.products.length ? (
          <div className={tileGrid}>
            {data.products.map((p, i) => (
              <ProductTile key={p.id} product={p} index={i} />
            ))}
          </div>
        ) : (
          <NoCampaigns />
        )}
      </Section>

      <Section title="Builders you back">
        {data.backings.length ? (
          <div className="grid gap-3 lg:grid-cols-2 2xl:grid-cols-3">
            {data.backings.map((b) => (
              <Link
                key={b.id}
                href="/app/backings"
                onPointerEnter={() => prefetch("/me/backings")}
                className="lift flex items-start gap-4 rounded-3xl bg-card p-4 shadow-soft ring-1 ring-foreground/[0.07] outline-none focus-visible:ring-3 focus-visible:ring-ring/50 sm:p-5"
              >
                <FoundingSeal number={b.badge_number ?? undefined} size={64} className="shrink-0" />
                <span className="flex min-w-0 flex-1 flex-col gap-1">
                  <span className="truncate font-heading text-lg">{b.product_name}</span>
                  <span className="line-clamp-2 text-sm text-pretty text-foreground/75">{b.campaign_headline}</span>
                  <span className="truncate text-xs text-muted-foreground">
                    by {b.builder_name} · Backed {shortDate(b.backed_at)}
                  </span>
                  <span className="mt-2 flex flex-wrap gap-2 text-xs">
                    <span className="rounded-full bg-secondary px-2.5 py-1 text-secondary-foreground">
                      {b.badge_number ? `Founding backer #${b.badge_number}` : "Referred customer"}
                    </span>
                    <span className="tabular rounded-full bg-accent px-2.5 py-1 text-accent-foreground">
                      {b.referrals
                        ? `${b.referrals} ${b.referrals === 1 ? "referral" : "referrals"} · ${money(b.earned_cents)} earned`
                        : "No referrals yet"}
                    </span>
                  </span>
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
      </Section>
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-5">
      <h2 className="text-2xl">{title}</h2>
      {children}
    </section>
  );
}
