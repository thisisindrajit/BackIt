"use client";

import Link from "next/link";
import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { ErrorState } from "@/components/backit/error-state";
import { PageHeader } from "@/components/backit/page-header";
import { CardsSkeleton } from "@/components/backit/skeletons";
import { BackingCard } from "@/components/backer/backing-card";
import { useApi } from "@/hooks/use-api";
import type { Backing, Me } from "@/lib/api/types";

export default function BackingsPage() {
  const backings = useApi<Backing[]>("/me/backings");
  const me = useApi<Me>("/me");
  const loaded = Boolean(backings.data);

  useEffect(() => {
    if (!loaded) return;
    const id = window.location.hash.slice(1);
    const el = id.startsWith("backing-") ? document.getElementById(id) : null;
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
    el.dataset.highlight = "";
    const t = window.setTimeout(() => delete el.dataset.highlight, 2400);
    return () => {
      window.clearTimeout(t);
      delete el.dataset.highlight;
    };
  }, [loaded]);

  return (
    <>
      <PageHeader title="Backing" description="Your founding badges, referral links, and what you’ve earned from them." />
      {me.data && !me.data.profile.payout_email ? (
        <p className="rounded-2xl bg-accent px-5 py-4 text-sm text-accent-foreground">
          Add a PayPal email in{" "}
          <Link href="/app/settings" className="font-medium underline underline-offset-4">
            Settings
          </Link>{" "}
          so builders can pay your rewards.
        </p>
      ) : null}
      {backings.error ? (
        <ErrorState error={backings.error} onRetry={backings.reload} />
      ) : !backings.data ? (
        <CardsSkeleton />
      ) : backings.data.length ? (
        <div className="flex flex-col gap-8">
          {backings.data.map((b) => (
            <BackingCard key={b.id} backing={b} />
          ))}
        </div>
      ) : (
        <Empty className="rounded-3xl bg-muted/60">
          <EmptyHeader>
            <EmptyTitle>You haven’t backed anything yet</EmptyTitle>
            <EmptyDescription>Find a campaign you like and buy a founding spot. Your badge and referral link will live here.</EmptyDescription>
          </EmptyHeader>
          <EmptyContent>
            <Button render={<Link href="/app/explore" />} nativeButton={false}>
              Explore campaigns
            </Button>
          </EmptyContent>
        </Empty>
      )}
    </>
  );
}
