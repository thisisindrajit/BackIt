import { Suspense } from "react";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { Skeleton } from "@/components/ui/skeleton";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/backit/app-sidebar";
import { Wordmark } from "@/components/backit/wordmark";
import { auth } from "@/lib/auth";

async function Guarded({ children }: { children: React.ReactNode }) {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) redirect("/sign-in?next=/app");
  return (
    <SidebarProvider>
      <AppSidebar name={session.user.name} email={session.user.email} />
      <SidebarInset>
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 rounded-t-xl bg-background/85 px-4 backdrop-blur-md md:hidden">
          <SidebarTrigger />
          <Wordmark href="/app" />
        </header>
        <div className="stagger mx-auto flex w-full max-w-5xl flex-1 flex-col gap-10 px-4 py-8 sm:px-8 md:py-12">{children}</div>
      </SidebarInset>
    </SidebarProvider>
  );
}

export default function AppLayout({ children }: LayoutProps<"/app">) {
  return (
    <div className="flex min-h-svh flex-col">
      <Suspense
        fallback={
          <div className="flex min-h-svh bg-sidebar">
            <div className="hidden w-64 shrink-0 md:block" />
            <div className="m-2 flex flex-1 flex-col gap-8 rounded-xl bg-background px-8 py-12 shadow-sm">
              <Skeleton className="h-10 w-64" />
              <Skeleton className="h-48" />
            </div>
          </div>
        }
      >
        <Guarded>{children}</Guarded>
      </Suspense>
    </div>
  );
}
