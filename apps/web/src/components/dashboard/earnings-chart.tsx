"use client";

import { useState } from "react";
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { type ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import { money } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Activity } from "@/lib/api/types";

type Series = "sales_cents" | "earned_cents" | "sent_cents";

const config = {
  sales_cents: { label: "Sales", color: "var(--chart-1)" },
  earned_cents: { label: "Rewards earned", color: "var(--chart-3)" },
  sent_cents: { label: "Rewards sent", color: "var(--chart-5)" },
} satisfies ChartConfig;

const hints: Record<Series, string> = {
  sales_cents: "Paid orders on your campaigns",
  earned_cents: "Referral rewards from builders you back",
  sent_cents: "Rewards you paid out to your backers",
};

const series = Object.keys(config) as Series[];

const weekLabel = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
const fmtWeek = (week: string) => weekLabel.format(new Date(`${week}T00:00:00Z`));
const axisMoney = (cents: number) => (cents >= 100_000 ? `$${Math.round(cents / 100_000)}k` : `$${Math.round(cents / 100)}`);

export function EarningsChart({ activity }: { activity: Activity }) {
  const { weeks, totals } = activity;
  const [picked, setPicked] = useState<Series | null>(null);
  const active = picked ?? series.find((s) => totals[s] > 0) ?? "sales_cents";
  const empty = series.every((s) => totals[s] === 0);

  return (
    <div className="flex flex-col overflow-hidden rounded-3xl bg-card shadow-soft ring-1 ring-foreground/[0.07]">
      <div role="tablist" aria-label="Chart series" className="grid grid-cols-3 border-b border-foreground/[0.07]">
        {series.map((s) => (
          <button
            key={s}
            type="button"
            role="tab"
            aria-selected={s === active}
            onClick={() => setPicked(s)}
            className={cn(
              "relative flex min-w-0 flex-col items-start gap-1 px-3 py-4 text-left outline-none transition-colors duration-150 not-first:border-l not-first:border-foreground/[0.07] focus-visible:bg-muted sm:px-6 sm:py-5",
              s === active ? "bg-accent/60" : "hover:bg-muted/60",
            )}
          >
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground sm:text-sm">
              <span aria-hidden className="size-2 shrink-0 rounded-full" style={{ background: config[s].color }} />
              <span className="truncate">{config[s].label}</span>
            </span>
            <span className="tabular font-heading text-xl leading-none sm:text-3xl">{money(totals[s])}</span>
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-2 px-2 pt-4 pb-3 sm:px-5 sm:pt-5">
        <p className="px-2 text-sm text-muted-foreground sm:px-1">
          {hints[active]} · last {weeks.length} weeks
        </p>
        {empty ? (
          <div className="grid h-56 place-items-center px-6 text-center text-sm text-muted-foreground sm:h-64">
            Nothing yet. Your first sale or referral reward will show up here.
          </div>
        ) : (
          <ChartContainer config={config} className="aspect-auto h-56 w-full sm:h-64">
            <AreaChart data={weeks} margin={{ left: 4, right: 12, top: 8 }}>
              <defs>
                <linearGradient id={`fill-${active}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={`var(--color-${active})`} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={`var(--color-${active})`} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="week" tickLine={false} axisLine={false} tickMargin={10} minTickGap={24} tickFormatter={fmtWeek} />
              <YAxis width={44} tickLine={false} axisLine={false} tickMargin={4} tickFormatter={axisMoney} allowDecimals={false} />
              <ChartTooltip
                cursor={{ stroke: "var(--border)" }}
                content={
                  <ChartTooltipContent
                    labelFormatter={(_, payload) => `Week of ${fmtWeek(payload?.[0]?.payload.week)}`}
                    formatter={(value, name) => (
                      <span className="flex w-full justify-between gap-4">
                        <span className="text-muted-foreground">{config[name as Series]?.label}</span>
                        <span className="tabular font-medium text-foreground">{money(Number(value))}</span>
                      </span>
                    )}
                  />
                }
              />
              <Area
                key={active}
                dataKey={active}
                type="monotone"
                stroke={`var(--color-${active})`}
                strokeWidth={2}
                fill={`url(#fill-${active})`}
                animationDuration={500}
              />
            </AreaChart>
          </ChartContainer>
        )}
      </div>
    </div>
  );
}
