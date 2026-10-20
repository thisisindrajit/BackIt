"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ChevronsUpDownIcon, HandHeartIcon, HouseIcon, LogOutIcon, PlusIcon, RocketIcon, SettingsIcon } from "lucide-react";
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
import { authClient } from "@/lib/auth-client";
import { clearTokenCache } from "@/hooks/use-api";
import { Wordmark } from "./wordmark";

const main = [
  { href: "/app", label: "Home", icon: HouseIcon, exact: true },
  { href: "/app/products", label: "Campaigns", icon: RocketIcon },
  { href: "/app/backings", label: "Backing", icon: HandHeartIcon },
];

export function AppSidebar({ name, email }: { name: string; email: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const { setOpenMobile } = useSidebar();
  const initials = name.split(" ").map((p) => p[0]).join("").slice(0, 2).toUpperCase() || "?";
  const isActive = (href: string, exact?: boolean) => (exact ? pathname === href : pathname.startsWith(href));

  async function signOut() {
    clearTokenCache();
    await authClient.signOut();
    router.push("/");
    router.refresh();
  }

  return (
    <Sidebar variant="inset">
      <SidebarHeader className="gap-4 px-3 pt-4">
        <Wordmark href="/app" />
        <Button
          render={<Link href="/app/products/new" onClick={() => setOpenMobile(false)} />}
          nativeButton={false}
          className="w-full justify-start"
        >
          <PlusIcon data-icon="inline-start" />
          New campaign
        </Button>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {main.map((l) => (
                <SidebarMenuItem key={l.href}>
                  <SidebarMenuButton
                    render={<Link href={l.href} onClick={() => setOpenMobile(false)} />}
                    isActive={isActive(l.href, l.exact)}
                    className="h-9 rounded-full px-3 transition-colors duration-150"
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
          <SidebarGroupLabel>Account</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton
                  render={<Link href="/app/settings" onClick={() => setOpenMobile(false)} />}
                  isActive={isActive("/app/settings")}
                  className="h-9 rounded-full px-3 transition-colors duration-150"
                >
                  <SettingsIcon />
                  <span>Settings</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="p-3">
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
              <DropdownMenuItem onClick={() => router.push("/app/settings")}>
                <SettingsIcon />
                Settings
              </DropdownMenuItem>
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
