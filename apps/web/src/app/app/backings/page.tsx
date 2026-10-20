"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/backit/error-state";
import { PageHeader } from "@/components/backit/page-header";
import { BackingCard } from "@/components/backer/backing-card";
import { useApi } from "@/hooks/use-api";
import type { Backing, Me } from "@/lib/api/types";

export default function BackingsPage() {
  const backings = useApi<Backing[]>("/me/backings");
  const me = useApi<Me>("/me");

  return (
    <>
      <PageHeader title="Backing" description="Your founding badges, referral links, and what you've earned from them." />
      {me.data && !me.data.profile.payout_email ? (
        <p className="rounded-lg bg-accent px-4 py-3 text-sm text-accent-foreground">
          Add a PayPal email in{" "}
          <Link href="/app/settings" className="font-medium underline underline-offset-4">
            Settings
          </Link>{" "}
          so builders can pay your commissions.
        </p>
      ) : null}
      {backings.error ? (
        <ErrorState error={backings.error} onRetry={backings.reload} />
      ) : backings.loading && !backings.data ? (
        <Skeleton className="h-64" />
      ) : backings.data?.length ? (
        <div className="flex flex-col gap-8">
          {backings.data.map((b) => (
            <BackingCard key={b.id} backing={b} />
          ))}
        </div>
      ) : (
        <Empty className="border">
          <EmptyHeader>
            <EmptyTitle>You haven’t backed anything yet</EmptyTitle>
            <EmptyDescription>Buy a founding spot on a builder’s campaign page. Your badge and referral link will live here.</EmptyDescription>
          </EmptyHeader>
          <EmptyContent>
            <Button render={<Link href="/" />} nativeButton={false} variant="outline">
              How BackIt works
            </Button>
          </EmptyContent>
        </Empty>
      )}
    </>
  );
}
