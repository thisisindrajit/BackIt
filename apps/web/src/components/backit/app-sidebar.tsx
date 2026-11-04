"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { ChevronsUpDownIcon, LogOutIcon, PlusIcon } from "lucide-react";
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
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { usePrefetch } from "@/hooks/use-api";
import { initialsOf, isNavActive, mainNav as main, settingsNav, useSignOut } from "./app-nav";
import { NotificationBell } from "./notification-bell";
import { Wordmark } from "./wordmark";

export function AppSidebar({ name, email }: { name: string; email: string }) {
  const pathname = usePathname();
  const { setOpenMobile } = useSidebar();
  const signOut = useSignOut();
  const prefetch = usePrefetch();

  useEffect(() => prefetch("/me"), [prefetch]);
  const initials = initialsOf(name);
  const isActive = (href: string, exact?: boolean) => isNavActive(pathname, href, exact);

  return (
    <Sidebar variant="inset">
      <SidebarHeader className="gap-5 px-4 pt-5 pb-2">
        <div className="flex items-center justify-between pl-3">
          <Wordmark href="/app" />
          <NotificationBell side="bottom" align="start" />
        </div>
        <Button
          render={<Link href="/app/products/new" onClick={() => setOpenMobile(false)} />}
          nativeButton={false}
          size="lg"
          className="w-full"
        >
          <PlusIcon data-icon="inline-start" />
          New campaign
        </Button>
      </SidebarHeader>
      <SidebarContent className="gap-2 px-2">
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu className="gap-1">
              {main.map((l) => (
                <SidebarMenuItem key={l.href}>
                  <SidebarMenuButton
                    render={
                      <Link
                        href={l.href}
                        onClick={() => setOpenMobile(false)}
                        onPointerEnter={() => prefetch(...l.data)}
                        onFocus={() => prefetch(...l.data)}
                      />
                    }
                    isActive={isActive(l.href, l.exact)}
                    className="h-10 gap-3 rounded-full px-3 transition-colors duration-150"
                  >
                    <l.icon />
                    <span>{l.label}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
        <SidebarGroup>
          <SidebarGroupLabel className="px-3">Account</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu className="gap-1">
              <SidebarMenuItem>
                <SidebarMenuButton
                  render={<Link href={settingsNav.href} onClick={() => setOpenMobile(false)} onPointerEnter={() => prefetch(...settingsNav.data)} />}
                  isActive={isActive(settingsNav.href)}
                  className="h-10 gap-3 rounded-full px-3 transition-colors duration-150"
                >
                  <settingsNav.icon />
                  <span>{settingsNav.label}</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="p-4">
        <DropdownMenu>
          <DropdownMenuTrigger
            render={<SidebarMenuButton size="lg" className="rounded-2xl" aria-label="Account menu" />}
          >
            <Avatar className="size-8">
              <AvatarFallback className="bg-secondary font-serif text-sm italic">{initials}</AvatarFallback>
            </Avatar>
            <span className="flex min-w-0 flex-1 flex-col text-left leading-tight">
              <span className="truncate font-medium">{name}</span>
              <span className="truncate text-xs text-muted-foreground">{email}</span>
            </span>
            <ChevronsUpDownIcon className="ml-auto text-muted-foreground" />
          </DropdownMenuTrigger>
          <DropdownMenuContent side="top" align="start" className="w-60">
            <DropdownMenuGroup>
              <DropdownMenuLabel className="flex flex-col">
                <span className="text-foreground">{name}</span>
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
      </SidebarFooter>
    </Sidebar>
  );
}
