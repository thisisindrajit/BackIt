import Link from "next/link";
import { Suspense } from "react";
import { headers } from "next/headers";
import { Button } from "@/components/ui/button";
import { auth } from "@/lib/auth";
import { Wordmark } from "./wordmark";

async function SessionNav() {
  const session = await auth.api.getSession({ headers: await headers() }).catch(() => null);
  if (session) {
    return (
      <Button render={<Link href="/app" />} nativeButton={false}>
        Open dashboard
      </Button>
    );
  }
  return (
    <>
      <Button render={<Link href="/sign-in" />} nativeButton={false} variant="ghost">
        Sign in
      </Button>
      <Button render={<Link href="/sign-up" />} nativeButton={false}>
        <span className="sm:hidden">Start</span>
        <span className="hidden sm:inline">Start a campaign</span>
      </Button>
    </>
  );
}

const links = [
  { href: "/#how-it-works", label: "How it works" },
  { href: "/#why", label: "Why BackIt" },
  { href: "/#pricing", label: "Pricing" },
];

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-30 bg-background/80 backdrop-blur-md">
      <div className="page-shell grid h-16 grid-cols-[1fr_auto] items-center gap-3 md:grid-cols-[1fr_auto_1fr]">
        <Wordmark />
        <nav aria-label="Main" className="hidden items-center gap-1 md:flex">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="rounded-full px-3.5 py-2 text-sm text-foreground/70 transition-colors duration-150 hover:bg-muted hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
            >
              {l.label}
            </Link>
          ))}
        </nav>
        <div className="flex shrink-0 items-center justify-end gap-1">
          <Suspense>
            <SessionNav />
          </Suspense>
        </div>
      </div>
    </header>
  );
}
