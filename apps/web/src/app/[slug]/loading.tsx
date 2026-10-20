import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div className="mx-auto grid w-full max-w-5xl gap-12 px-4 py-24 sm:px-6 md:grid-cols-[1fr_22rem]">
      <div className="flex flex-col gap-4">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-12 w-4/5" />
        <Skeleton className="h-6 w-3/5" />
        <Skeleton className="mt-6 h-40" />
      </div>
      <Skeleton className="h-80" />
    </div>
  );
}
