"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { ExternalLinkIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ErrorState } from "@/components/backit/error-state";
import { PageHeader } from "@/components/backit/page-header";
import { StatusBadge } from "@/components/backit/status-badge";
import { CampaignTab } from "@/components/builder/campaign-tab";
import { PayoutsTab } from "@/components/builder/payouts-tab";
import { SalesTab } from "@/components/builder/sales-tab";
import { SetupTab } from "@/components/builder/setup-tab";
import { WebhooksTab } from "@/components/builder/webhooks-tab";
import { useApi } from "@/hooks/use-api";
import type { Product } from "@/lib/api/types";

const tabs = ["setup", "campaign", "sales", "payouts", "webhooks"] as const;

export default function ProductPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const params = useSearchParams();
  const tab = tabs.find((t) => t === params.get("tab")) ?? "setup";
  const { data: product, error, loading, reload } = useApi<Product>(`/products/${id}`);

  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (loading && !product) return <Skeleton className="h-64" />;
  if (!product) return null;

  const campaign = product.campaign;

  return (
    <>
      <PageHeader
        title={product.name}
        description={
          <span className="flex flex-wrap items-center gap-2">
            {campaign ? <StatusBadge status={campaign.status} /> : <StatusBadge status="draft" />}
            <span>{campaign ? `backit.club/${campaign.slug}` : "Campaign not created yet"}</span>
          </span>
        }
        actions={
          campaign?.status === "published" ? (
            <Button render={<Link href={`/${campaign.slug}`} target="_blank" />} nativeButton={false} variant="outline">
              View public page
              <ExternalLinkIcon data-icon="inline-end" />
            </Button>
          ) : null
        }
      />
      <Tabs value={tab} onValueChange={(v) => router.replace(`/app/products/${id}?tab=${v}`, { scroll: false })}>
        <TabsList className="w-full sm:w-fit *:data-[slot=tabs-trigger]:px-1.5 *:data-[slot=tabs-trigger]:text-xs sm:*:data-[slot=tabs-trigger]:px-3.5 sm:*:data-[slot=tabs-trigger]:text-sm">
          <TabsTrigger value="setup">Setup</TabsTrigger>
          <TabsTrigger value="campaign">Campaign</TabsTrigger>
          <TabsTrigger value="sales" disabled={!campaign}>Sales</TabsTrigger>
          <TabsTrigger value="payouts" disabled={!campaign}>Payouts</TabsTrigger>
          <TabsTrigger value="webhooks">Webhooks</TabsTrigger>
        </TabsList>
        <TabsContent value="setup" className="pt-4">
          <SetupTab product={product} onChange={reload} />
        </TabsContent>
        <TabsContent value="campaign" className="pt-4">
          <CampaignTab product={product} onChange={reload} />
        </TabsContent>
        <TabsContent value="sales" className="pt-4">
          {tab === "sales" ? <SalesTab productId={product.id} /> : null}
        </TabsContent>
        <TabsContent value="payouts" className="pt-4">
          {tab === "payouts" ? <PayoutsTab productId={product.id} /> : null}
        </TabsContent>
        <TabsContent value="webhooks" className="pt-4">
          {tab === "webhooks" ? <WebhooksTab productId={product.id} /> : null}
        </TabsContent>
      </Tabs>
    </>
  );
}
