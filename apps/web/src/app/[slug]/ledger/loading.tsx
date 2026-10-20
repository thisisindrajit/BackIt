import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-24 sm:px-6">
      <Skeleton className="h-9 w-56" />
      <Skeleton className="h-64" />
    </div>
  );
}
