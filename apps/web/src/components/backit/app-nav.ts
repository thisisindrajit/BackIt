"use client";

import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { CompassIcon, HandHeartIcon, HouseIcon, RocketIcon, SettingsIcon } from "lucide-react";
import { authClient } from "@/lib/auth-client";
import { clearTokenCache } from "@/hooks/use-api";

export type NavItem = {
  href: string;
  label: string;
  icon: typeof HouseIcon;
  exact?: boolean;
  data: string[];
};

export const mainNav: NavItem[] = [
  { href: "/app", label: "Home", icon: HouseIcon, exact: true, data: ["/me"] },
  { href: "/app/explore", label: "Explore", icon: CompassIcon, data: [] },
  { href: "/app/products", label: "Campaigns", icon: RocketIcon, data: ["/me"] },
  { href: "/app/backings", label: "Backing", icon: HandHeartIcon, data: ["/me/backings", "/me"] },
];

export const settingsNav: NavItem = { href: "/app/settings", label: "Settings", icon: SettingsIcon, data: ["/me"] };

export function isNavActive(pathname: string, href: string, exact?: boolean) {
  return exact ? pathname === href : pathname === href || pathname.startsWith(`${href}/`);
}

export function initialsOf(name: string) {
  return name.split(" ").map((p) => p[0]).join("").slice(0, 2).toUpperCase() || "?";
}

export function useSignOut() {
  const router = useRouter();
  const queryClient = useQueryClient();
  return async function signOut() {
    clearTokenCache();
    await authClient.signOut();
    queryClient.clear();
    router.push("/");
    router.refresh();
  };
}
