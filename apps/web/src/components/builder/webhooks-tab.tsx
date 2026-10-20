"use client";

import { Button } from "@/components/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ErrorState } from "@/components/backit/error-state";
import { StatusBadge } from "@/components/backit/status-badge";
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

  return (
    <div className="flex flex-col gap-10">
      <section className="flex flex-col gap-3">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-lg font-semibold">Deliveries to your app</h2>
          <Button variant="outline" size="sm" onClick={deliveries.reload}>
            Refresh
          </Button>
        </div>
        {deliveries.error ? (
          <ErrorState error={deliveries.error} onRetry={deliveries.reload} />
        ) : deliveries.loading && !deliveries.data ? (
          <Skeleton className="h-32" />
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
          <h2 className="text-lg font-semibold">Review flags</h2>
          <p className="text-sm text-muted-foreground">Rule-based checks such as self-referral. Flagged commissions are held from payouts until reviewed.</p>
        </div>
        {flags.data?.length ? (
          <ul className="flex flex-col divide-y rounded-lg border">
            {flags.data.map((f) => (
              <li key={f.id} className="flex flex-col gap-1 p-3">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{f.rule.replace(/_/g, " ")}</span>
                  <StatusBadge status={f.status} />
                  <span className="text-xs text-muted-foreground">{f.severity} severity</span>
                </div>
                {f.explanation ? <p className="text-sm text-muted-foreground">{f.explanation}</p> : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">{flags.loading ? "Loading…" : "Nothing flagged."}</p>
        )}
      </section>
    </div>
  );
}
