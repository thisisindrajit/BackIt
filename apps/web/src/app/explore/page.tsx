import type { Metadata } from "next";
import { Suspense } from "react";
import { SiteFooter } from "@/components/backit/site-footer";
import { SiteHeader } from "@/components/backit/site-header";
import { ExploreResults, ExploreResultsSkeleton } from "@/components/explore/explore-results";

export const metadata: Metadata = {
  title: "Explore campaigns",
  description: "Back indie products early. Founding backers get an early deal and a reward for every friend who buys.",
};

export default function ExplorePage({ searchParams }: PageProps<"/explore">) {
  return (
    <div className="flex min-h-svh flex-col">
      <SiteHeader />
      <main className="page-shell flex-1 py-10 md:py-16">
        <div className="mx-auto flex w-full max-w-4xl flex-col gap-10">
          <header className="rise flex flex-col gap-3">
            <h1 className="text-5xl leading-[1.02] sm:text-6xl">
              Back something <em>early</em>.
            </h1>
            <p className="max-w-prose text-lg text-pretty text-muted-foreground">
              Indie products raising from their first fans. Founding backers get an early deal, plus a reward for every friend who buys.
            </p>
          </header>
          <Suspense fallback={<ExploreResultsSkeleton />}>
            <ExploreResults searchParams={searchParams} basePath="/explore" />
          </Suspense>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
