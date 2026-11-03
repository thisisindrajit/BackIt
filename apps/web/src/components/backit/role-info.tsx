"use client";

import { InfoIcon } from "lucide-react";
import { Popover, PopoverContent, PopoverDescription, PopoverHeader, PopoverTitle, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

export type Role = "founding" | "referral";

const roles: Record<Role, { title: string; body: string }> = {
  founding: {
    title: "Founding backer",
    body: "You bought one of the first numbered spots. You keep the product, a permanent badge, and a referral link that earns you a reward for every friend who buys.",
  },
  referral: {
    title: "Referral buyer",
    body: "You bought through a backer’s link and got a discount. You also get your own referral link, so you can earn when friends buy too.",
  },
};

export function RoleInfo({ role, className }: { role: Role; className?: string }) {
  const r = roles[role];
  return (
    <Popover>
      <PopoverTrigger
        aria-label={`What is a ${r.title.toLowerCase()}?`}
        onClick={(e) => e.stopPropagation()}
        className={cn(
          "inline-flex size-5 shrink-0 items-center justify-center rounded-full text-current opacity-70 outline-none transition-opacity hover:opacity-100 focus-visible:opacity-100 focus-visible:ring-3 focus-visible:ring-ring/50",
          className,
        )}
      >
        <InfoIcon className="size-3.5" aria-hidden />
      </PopoverTrigger>
      <PopoverContent side="top" className="w-64">
        <PopoverHeader>
          <PopoverTitle className="font-medium">{r.title}</PopoverTitle>
          <PopoverDescription className="text-pretty">{r.body}</PopoverDescription>
        </PopoverHeader>
      </PopoverContent>
    </Popover>
  );
}

export function RoleBadge({ role, label, className }: { role: Role; label?: string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full py-1 pr-1 pl-2.5 text-xs",
        role === "referral"
          ? "bg-accent text-primary-deep ring-1 ring-primary-deep/25"
          : "bg-secondary text-secondary-foreground",
        className,
      )}
    >
      {label ?? roles[role].title}
      <RoleInfo role={role} />
    </span>
  );
}
