import { Suspense } from "react";
import { redirect } from "next/navigation";
import { Skeleton } from "@/components/ui/skeleton";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/backit/app-sidebar";
import { BottomBar, MobileHeader } from "@/components/backit/mobile-nav";
import { PageHeaderSkeleton, TileGridSkeleton } from "@/components/backit/skeletons";
import { getSession } from "@/lib/session";

async function Guarded({ children }: { children: React.ReactNode }) {
  const session = await getSession();
  if (!session) redirect("/sign-in?next=/app");
  return (
    <SidebarProvider>
      <AppSidebar name={session.user.name} email={session.user.email} />
      <SidebarInset>
        <MobileHeader name={session.user.name} email={session.user.email} />
        <div className="stagger safe-x flex w-full flex-1 flex-col gap-10 pt-6 pb-[calc(6rem+env(safe-area-inset-bottom))] sm:[--gutter:2rem] md:py-10 xl:[--gutter:3rem]">
          {children}
        </div>
      </SidebarInset>
      <BottomBar />
    </SidebarProvider>
  );
}

export default function AppLayout({ children }: LayoutProps<"/app">) {
  return (
    <div className="flex min-h-svh flex-col">
      <Suspense
        fallback={
          <div className="flex min-h-svh bg-sidebar" aria-busy>
            <div className="hidden w-64 shrink-0 flex-col gap-5 px-4 pt-5 md:flex">
              <Skeleton className="mx-3 h-8 w-28 rounded-xl" />
              <Skeleton className="h-11 rounded-full" />
              <div className="flex flex-col gap-1 px-2 pt-2">
                {[0, 1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-10 rounded-full" />
                ))}
              </div>
            </div>
            <div className="safe-x flex flex-1 flex-col gap-10 bg-background pt-[calc(5rem+env(safe-area-inset-top))] pb-8 sm:[--gutter:2rem] md:m-2 md:ml-0 md:rounded-xl md:py-10 md:shadow-sm xl:[--gutter:3rem]">
              <PageHeaderSkeleton />
              <TileGridSkeleton />
            </div>
          </div>
        }
      >
        <Guarded>{children}</Guarded>
      </Suspense>
    </div>
  );
}
