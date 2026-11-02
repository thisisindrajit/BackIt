import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/client";
import { listPublicCampaigns } from "@/lib/api/server";
import { CampaignList, CampaignListSkeleton, parseSort, SortTabs } from "./campaign-list";

type Search = Promise<Record<string, string | string[] | undefined>>;

/** Reads the sort from the URL, so render it inside a Suspense boundary. */
export async function ExploreResults({ searchParams, basePath }: { searchParams: Search; basePath: string }) {
  const sort = parseSort((await searchParams).sort);
  let campaigns;
  try {
    campaigns = await listPublicCampaigns(sort);
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    return (
      <Empty className="rounded-3xl bg-muted/60">
        <EmptyHeader>
          <EmptyTitle>Campaigns didn’t load</EmptyTitle>
          <EmptyDescription>{e.message}</EmptyDescription>
        </EmptyHeader>
        <EmptyContent>
          <Button render={<Link href={`${basePath}?sort=${sort}`} />} nativeButton={false} variant="outline">
            Try again
          </Button>
        </EmptyContent>
      </Empty>
    );
  }
  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between gap-4">
        <SortTabs basePath={basePath} current={sort} />
        <p className="tabular text-sm text-muted-foreground">
          {campaigns.length} live {campaigns.length === 1 ? "campaign" : "campaigns"}
        </p>
      </div>
      <CampaignList campaigns={campaigns} />
    </div>
  );
}

export function ExploreResultsSkeleton() {
  return (
    <div className="flex flex-col gap-5">
      <Skeleton className="h-10 w-48 rounded-full" />
      <CampaignListSkeleton />
    </div>
  );
}
