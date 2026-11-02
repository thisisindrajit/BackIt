import type { Metadata } from "next";
import { Suspense } from "react";
import { PageHeader } from "@/components/backit/page-header";
import { ExploreResults, ExploreResultsSkeleton } from "@/components/explore/explore-results";

export const metadata: Metadata = { title: "Explore" };

export default function AppExplorePage({ searchParams }: PageProps<"/app/explore">) {
  return (
    <>
      <PageHeader
        title="Explore"
        description="Products raising from their first backers. Back one early, then earn a reward when friends buy."
      />
      <Suspense fallback={<ExploreResultsSkeleton />}>
        <ExploreResults searchParams={searchParams} basePath="/app/explore" />
      </Suspense>
    </>
  );
}
