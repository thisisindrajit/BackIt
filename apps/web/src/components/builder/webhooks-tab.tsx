"use client";

import { Button } from "@/components/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ErrorState } from "@/components/backit/error-state";
import { StatusBadge } from "@/components/backit/status-badge";
import { TableSkeleton } from "@/components/backit/skeletons";
import { Skeleton } from "@/components/ui/skeleton";
import { authedApi, useApi } from "@/hooks/use-api";
import { shortDate } from "@/lib/format";
import type { RiskFlag, WebhookDelivery } from "@/lib/api/types";
import { useAction } from "@/hooks/use-action";

export function WebhooksTab({ productId }: { productId: string }) {
  const deliveries = useApi<WebhookDelivery[]>(`/products/${productId}/webhook-deliveries`);
  const flags = useApi<RiskFlag[]>(`/products/${productId}/risk-flags`);
  const { pending, run } = useAction();

  async function retry(id: string) {
    const res = await run(id, () => authedApi(`/webhook-deliveries/${id}/retry`, { method: "POST" }), "Retry queued");
    if (res) deliveries.reload();
  }

  async function decide(id: string, decision: "clear" | "confirm") {
    const res = await run(
      `${decision}-${id}`,
      () => authedApi<RiskFlag>(`/risk-flags/${id}/decision`, { method: "POST", body: { decision } }),
      decision === "clear" ? "Cleared. Commissions return to the next payout." : "Confirmed. Those commissions stay blocked.",
    );
    if (res) flags.reload();
  }

  return (
    <div className="flex flex-col gap-10">
      <section className="flex flex-col gap-3">
        <h2 className="text-2xl">Deliveries to your app</h2>
        {deliveries.error ? (
          <ErrorState error={deliveries.error} onRetry={deliveries.reload} />
        ) : !deliveries.data ? (
          <TableSkeleton rows={3} />
        ) : deliveries.data?.length ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Event</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right max-sm:hidden">Attempts</TableHead>
                <TableHead className="max-sm:hidden">Last response</TableHead>
                <TableHead className="max-sm:hidden">Created</TableHead>
                <TableHead className="sr-only">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {deliveries.data.map((d) => (
                <TableRow key={d.id}>
                  <TableCell className="flex flex-col">
                    <span className="font-mono text-xs">{d.event_type}</span>
                    <span className="font-mono text-xs text-muted-foreground max-sm:hidden">{d.event_id}</span>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={d.state} />
                  </TableCell>
                  <TableCell className="tabular text-right max-sm:hidden">{d.attempts}</TableCell>
                  <TableCell className="max-w-64 truncate text-muted-foreground max-sm:hidden" title={d.last_error ?? undefined}>
                    {d.last_status_code ? `HTTP ${d.last_status_code}` : d.last_error ?? "None yet"}
                  </TableCell>
                  <TableCell className="text-muted-foreground max-sm:hidden">{shortDate(d.created_at)}</TableCell>
                  <TableCell className="text-right">
                    {d.state === "failed" || d.state === "dead" ? (
                      <Button variant="ghost" size="sm" onClick={() => retry(d.id)} disabled={pending === d.id}>
                        Retry
                      </Button>
                    ) : null}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <Empty className="border">
            <EmptyHeader>
              <EmptyTitle>No deliveries yet</EmptyTitle>
              <EmptyDescription>Send a test ping from Setup. Purchases and refunds appear here with their delivery status.</EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <h2 className="text-2xl">Review flags</h2>
          <p className="text-sm text-muted-foreground">
            Rule checks like self-referral, plus backers you held after the risk review. Clear to pay them, or confirm to keep their commissions blocked.
          </p>
        </div>
        {!flags.data && !flags.error ? (
          <Skeleton className="h-16 rounded-lg" aria-hidden />
        ) : flags.data?.length ? (
          <ul className="flex flex-col divide-y rounded-lg border">
            {flags.data.map((f) => (
              <li key={f.id} className="flex flex-col gap-1 p-3">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{f.rule.replace(/_/g, " ")}</span>
                  <StatusBadge status={f.status} />
                  <span className="text-xs text-muted-foreground">{f.severity} severity</span>
                </div>
                {f.explanation ? <p className="text-sm text-muted-foreground">{f.explanation}</p> : null}
                {typeof f.evidence.ai_summary === "string" ? (
                  <p className="text-sm">
                    <span className="text-muted-foreground">Risk review: </span>
                    {f.evidence.ai_summary}
                  </p>
                ) : null}
                {f.status === "open" ? (
                  <div className="flex gap-2 pt-1">
                    <Button size="sm" variant="outline" onClick={() => decide(f.id, "clear")} disabled={pending !== null}>
                      Clear and pay
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => decide(f.id, "confirm")} disabled={pending !== null}>
                      Confirm and block
                    </Button>
                  </div>
                ) : f.decided_at ? (
                  <span className="text-xs text-muted-foreground">Decided {shortDate(f.decided_at)}</span>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">Nothing flagged.</p>
        )}
      </section>
    </div>
  );
}
