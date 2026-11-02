"use client";

import { ErrorState } from "@/components/backit/error-state";
import { PageHeader } from "@/components/backit/page-header";
import { NoCampaigns, ProductTile } from "@/components/backit/product-tile";
import { TileGridSkeleton, tileGrid } from "@/components/backit/skeletons";
import { useApi } from "@/hooks/use-api";
import type { Me } from "@/lib/api/types";

export default function ProductsPage() {
  const { data, error, reload } = useApi<Me>("/me");
  return (
    <>
      <PageHeader title="Campaigns" description="Each product runs one founding-backer campaign." />
      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : !data ? (
        <TileGridSkeleton count={4} />
      ) : data.products.length ? (
        <div className={`stagger ${tileGrid}`}>
          {data.products.map((p, i) => (
            <ProductTile key={p.id} product={p} index={i} />
          ))}
        </div>
      ) : (
        <NoCampaigns />
      )}
    </>
  );
}
