"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BellIcon, FlagIcon, FlagOffIcon, HandCoinsIcon, MessageSquareReplyIcon, RocketIcon, ShoppingBagIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { apiKey, apiQuery, authedApi } from "@/hooks/use-api";
import type { Notification, NotificationList } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const PATH = "/me/notifications";

const icons: Record<Notification["kind"], typeof BellIcon> = {
  sale: ShoppingBagIcon,
  referral_sale: HandCoinsIcon,
  campaign_live: RocketIcon,
  campaign_ended: FlagOffIcon,
  access_report: FlagIcon,
  access_report_reply: MessageSquareReplyIcon,
};

const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto", style: "short" });

function ago(iso: string) {
  const seconds = Math.round((new Date(iso).getTime() - Date.now()) / 1000);
  const steps: [Intl.RelativeTimeFormatUnit, number][] = [
    ["second", 60], ["minute", 60], ["hour", 24], ["day", 7], ["week", 4.35], ["month", 12], ["year", Infinity],
  ];
  let value = seconds;
  for (const [unit, size] of steps) {
    if (Math.abs(value) < size) return unit === "second" ? "just now" : rtf.format(Math.round(value), unit);
    value /= size;
  }
  return "";
}

export function NotificationBell({ side = "bottom", align = "end" }: {
  side?: "bottom" | "right";
  align?: "start" | "end";
}) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const { data } = useQuery({
    ...apiQuery<NotificationList>(PATH),
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
  });
  const unread = data?.unread_count ?? 0;
  const items = data?.items ?? [];

  async function markAllRead() {
    if (!unread) return;
    // Only the bell reads this data, so skip the app-wide refresh that other writes trigger.
    const next = await authedApi<NotificationList>(`${PATH}/read`, { method: "POST", body: {}, readOnly: true });
    queryClient.setQueryData(apiKey(PATH), next);
  }

  function onOpenChange(next: boolean) {
    setOpen(next);
    // Mark read when the panel closes, so new items stay highlighted while it's open.
    if (!next) void markAllRead().catch(() => {});
  }

  return (
    <Popover open={open} onOpenChange={onOpenChange}>
      <PopoverTrigger
        render={
          <Button
            variant="ghost"
            size="icon"
            className="relative rounded-full"
            aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
          />
        }
      >
        <BellIcon />
        {unread > 0 && (
          <span className="absolute top-1 right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[10px] leading-none font-semibold text-primary-foreground tabular-nums ring-2 ring-background">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </PopoverTrigger>
      <PopoverContent side={side} align={align} sideOffset={8} className="w-[min(22rem,calc(100vw-1.5rem))] gap-0 rounded-2xl p-0">
        <div className="flex items-baseline justify-between px-4 pt-4 pb-2">
          <p className="font-serif text-lg">Notifications</p>
          {unread > 0 && <p className="text-xs text-muted-foreground">{unread} new</p>}
        </div>
        {items.length === 0 ? (
          <div className="px-4 pt-2 pb-6 text-sm text-muted-foreground">
            Sales and launches will show up here.
          </div>
        ) : (
          <ul className="max-h-[min(26rem,70vh)] overflow-y-auto px-1.5 pb-1.5">
            {items.map((n) => {
              const Icon = icons[n.kind];
              const content = (
                <>
                  <span
                    className={cn(
                      "mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full",
                      n.read ? "bg-muted text-muted-foreground" : "bg-secondary text-foreground",
                    )}
                  >
                    <Icon className="size-4" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-baseline gap-2">
                      <span className="min-w-0 flex-1 truncate font-medium">{n.title}</span>
                      <span className="shrink-0 text-xs text-muted-foreground">{ago(n.created_at)}</span>
                    </span>
                    <span className="mt-0.5 line-clamp-2 block text-muted-foreground">
                      {n.body.split("\n")[0]}
                    </span>
                  </span>
                  {!n.read && <span aria-label="Unread" className="mt-2 size-2 shrink-0 rounded-full bg-primary" />}
                </>
              );
              const row = "flex gap-3 rounded-xl px-2.5 py-2.5 text-left transition-colors duration-150";
              return (
                <li key={n.id}>
                  {n.link ? (
                    <Link href={n.link} onClick={() => onOpenChange(false)} className={cn(row, "hover:bg-muted focus-visible:bg-muted focus-visible:outline-none")}>
                      {content}
                    </Link>
                  ) : (
                    <div className={row}>{content}</div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </PopoverContent>
    </Popover>
  );
}
