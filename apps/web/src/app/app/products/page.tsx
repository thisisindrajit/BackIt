"use client";

import Link from "next/link";
import { PlusIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/backit/error-state";
import { PageHeader } from "@/components/backit/page-header";
import { NewProductTile, ProductTile } from "@/components/backit/product-tile";
import { useApi } from "@/hooks/use-api";
import type { Me } from "@/lib/api/types";

export default function ProductsPage() {
  const { data, error, loading, reload } = useApi<Me>("/me");
  return (
    <>
      <PageHeader
        title="Campaigns"
        description="Each product runs one founding-backer campaign."
        actions={
          <Button render={<Link href="/app/products/new" />} nativeButton={false}>
            <PlusIcon data-icon="inline-start" />
            Add a product
          </Button>
        }
      />
      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : loading && !data ? (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          <Skeleton className="h-56 rounded-3xl" />
          <Skeleton className="h-56 rounded-3xl" />
        </div>
      ) : (
        <div className="stagger grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {data?.products.map((p, i) => <ProductTile key={p.id} product={p} index={i} />)}
          <NewProductTile />
        </div>
      )}
    </>
  );
}
