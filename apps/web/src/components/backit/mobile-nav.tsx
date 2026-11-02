"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogOutIcon, PlusIcon } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { usePrefetch } from "@/hooks/use-api";
import { cn } from "@/lib/utils";
import { initialsOf, isNavActive, mainNav, settingsNav, useSignOut } from "./app-nav";
import { Wordmark } from "./wordmark";

const tabs = [...mainNav, settingsNav];

/** Top bar for small screens: brand, a quick “new campaign”, and the account menu. */
export function MobileHeader({ name, email }: { name: string; email: string }) {
  const signOut = useSignOut();
  return (
    <header className="safe-x sticky top-0 z-30 flex items-center gap-2 bg-background/85 pt-[env(safe-area-inset-top)] backdrop-blur-md md:hidden">
      <div className="flex h-14 w-full items-center gap-2">
        <Wordmark href="/app" />
        <Button
          render={<Link href="/app/products/new" />}
          nativeButton={false}
          size="icon"
          className="ml-auto rounded-full"
          aria-label="New campaign"
        >
          <PlusIcon />
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger
            render={<Button variant="ghost" size="icon" className="rounded-full" aria-label="Account menu" />}
          >
            <Avatar className="size-8">
              <AvatarFallback className="bg-secondary font-serif text-sm italic">{initialsOf(name)}</AvatarFallback>
            </Avatar>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-60">
            <DropdownMenuGroup>
              <DropdownMenuLabel className="flex flex-col">
                <span className="truncate text-foreground">{name}</span>
                <span className="truncate font-normal">{email}</span>
              </DropdownMenuLabel>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              <DropdownMenuItem onClick={signOut}>
                <LogOutIcon />
                Sign out
              </DropdownMenuItem>
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}

/** Thumb-reach navigation for small screens; replaces the sidebar below `md`. */
export function BottomBar() {
  const pathname = usePathname();
  const prefetch = usePrefetch();
  return (
    <nav
      aria-label="Primary"
      className="safe-x fixed inset-x-0 bottom-0 z-30 border-t border-border/60 bg-background/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-md md:hidden"
    >
      <ul className="mx-auto grid h-16 max-w-md grid-cols-5">
        {tabs.map((t) => {
          const active = isNavActive(pathname, t.href, t.exact);
          return (
            <li key={t.href} className="flex">
              <Link
                href={t.href}
                aria-current={active ? "page" : undefined}
                onPointerEnter={() => prefetch(...t.data)}
                onTouchStart={() => prefetch(...t.data)}
                className={cn(
                  "group flex flex-1 flex-col items-center justify-center gap-1 text-[11px] font-medium outline-none select-none [-webkit-tap-highlight-color:transparent]",
                  active ? "text-foreground" : "text-muted-foreground",
                )}
              >
                <span
                  className={cn(
                    "flex h-7 w-12 items-center justify-center rounded-full transition-[background-color,transform] duration-150 ease-out group-active:scale-90 group-focus-visible:ring-2 group-focus-visible:ring-ring",
                    active && "bg-secondary",
                  )}
                >
                  <t.icon className="size-5" strokeWidth={active ? 2.25 : 1.75} />
                </span>
                {t.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
