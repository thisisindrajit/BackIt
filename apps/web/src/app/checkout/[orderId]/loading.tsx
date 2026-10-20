import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div className="mx-auto w-full max-w-xl px-4 py-24 sm:px-6">
      <Skeleton className="h-80" />
    </div>
  );
}
