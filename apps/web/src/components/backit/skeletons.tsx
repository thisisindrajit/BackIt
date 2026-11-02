import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export function PageHeaderSkeleton({ description = true }: { description?: boolean }) {
  return (
    <div className="flex flex-col gap-3" aria-hidden>
      <Skeleton className="h-10 w-64 max-w-full rounded-xl sm:h-11" />
      {description ? <Skeleton className="h-4 w-96 max-w-full" /> : null}
    </div>
  );
}

export function TileSkeleton() {
  return (
    <div className="flex flex-col overflow-hidden rounded-3xl ring-1 ring-foreground/[0.07]">
      <Skeleton className="h-28 rounded-none" />
      <div className="flex flex-col gap-4 px-5 pt-4 pb-5">
        <div className="flex flex-col gap-2">
          <Skeleton className="h-5 w-32" />
          <Skeleton className="h-4 w-52 max-w-full" />
        </div>
        <div className="flex flex-col gap-2">
          <Skeleton className="h-2 w-full rounded-full" />
          <Skeleton className="h-4 w-36" />
        </div>
      </div>
    </div>
  );
}

export const tileGrid = "grid gap-5 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4";

export function TileGridSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className={tileGrid} aria-hidden>
      {Array.from({ length: count }, (_, i) => (
        <TileSkeleton key={i} />
      ))}
    </div>
  );
}

export function RowCardSkeleton({ count = 2 }: { count?: number }) {
  return (
    <div className="grid gap-3 lg:grid-cols-2" aria-hidden>
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="flex items-center gap-4 rounded-3xl p-4 ring-1 ring-foreground/[0.07]">
          <Skeleton className="size-16 shrink-0 self-start rounded-full" />
          <div className="flex flex-1 flex-col gap-2">
            <Skeleton className="h-5 w-32 max-w-full" />
            <Skeleton className="h-4 w-56 max-w-full" />
            <Skeleton className="h-3 w-24" />
            <div className="mt-2 flex gap-2">
              <Skeleton className="h-6 w-28 rounded-full" />
              <Skeleton className="h-6 w-24 rounded-full" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export function StatsSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className={cn("grid grid-cols-2 gap-6", count === 5 ? "sm:grid-cols-5" : "sm:grid-cols-4")} aria-hidden>
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="flex flex-col gap-2">
          <Skeleton className="h-3.5 w-20" />
          <Skeleton className="h-7 w-24" />
        </div>
      ))}
    </div>
  );
}

export function TableSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="flex flex-col" aria-hidden>
      <div className="flex gap-6 border-b py-3">
        <Skeleton className="h-3.5 w-24" />
        <Skeleton className="h-3.5 w-16" />
        <Skeleton className="ml-auto h-3.5 w-16" />
      </div>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex items-center gap-6 border-b py-3.5 last:border-b-0">
          <Skeleton className="h-4 w-40 max-w-[40%]" />
          <Skeleton className="h-5 w-20 rounded-full" />
          <Skeleton className="ml-auto h-4 w-16" />
        </div>
      ))}
    </div>
  );
}

export function FormSectionsSkeleton({ sections = 2 }: { sections?: number }) {
  return (
    <div className="flex flex-col" aria-hidden>
      {Array.from({ length: sections }, (_, i) => (
        <div key={i} className="grid gap-6 border-t py-8 first:border-t-0 first:pt-0 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)] lg:gap-12">
          <div className="flex flex-col gap-2">
            <Skeleton className="h-6 w-32" />
            <Skeleton className="h-4 w-56 max-w-full" />
          </div>
          <div className="grid gap-6 xl:grid-cols-2">
            {[0, 1].map((j) => (
              <div key={j} className="flex flex-col gap-2">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-9 rounded-xl" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export function CardsSkeleton({ count = 2, className }: { count?: number; className?: string }) {
  return (
    <div className={cn("grid gap-6", className)} aria-hidden>
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="flex flex-col gap-5 rounded-3xl p-6 ring-1 ring-foreground/[0.07]">
          <div className="flex items-start justify-between gap-4">
            <div className="flex flex-col gap-2">
              <Skeleton className="h-6 w-48 max-w-full" />
              <Skeleton className="h-4 w-72 max-w-full" />
            </div>
            <Skeleton className="h-5 w-20 rounded-full" />
          </div>
          <Skeleton className="h-9 rounded-xl" />
          <div className="flex gap-8">
            <Skeleton className="h-12 w-20" />
            <Skeleton className="h-12 w-20" />
            <Skeleton className="h-12 w-20" />
          </div>
          <Skeleton className="h-10 rounded-xl" />
        </div>
      ))}
    </div>
  );
}
