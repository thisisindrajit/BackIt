"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ErrorState } from "@/components/backit/error-state";
import { Stat } from "@/components/backit/stat";
import { StatusBadge } from "@/components/backit/status-badge";
import { authedApi, useApi } from "@/hooks/use-api";
import { money, shortDate } from "@/lib/format";
import type { SalesSummary } from "@/lib/api/types";
import { ConfirmDialog } from "./confirm-dialog";
import { useAction } from "@/hooks/use-action";

export function SalesTab({ productId }: { productId: string }) {
  const { data, error, loading, reload } = useApi<SalesSummary>(`/products/${productId}/sales`);
  const { pending, run } = useAction();
  const [open, setOpen] = useState<string | null>(null);

  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (loading && !data) return <Skeleton className="h-48" />;
  if (!data) return null;
  const t = data.totals;

  async function refund(orderId: string) {
    const res = await run(
      orderId,
      () => authedApi(`/orders/${orderId}/refund`, { method: "POST", idempotencyKey: `refund-${orderId}` }),
      "Refund requested",
    );
    if (res) {
      setOpen(null);
      reload();
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <dl className="grid grid-cols-2 gap-6 sm:grid-cols-4">
        <Stat label="Captured" value={money(t.captured_cents)} hint={`${t.orders} ${t.orders === 1 ? "order" : "orders"}`} />
        <Stat label="Refunded" value={money(t.refunded_cents)} />
        <Stat label="BackIt fees" value={money(t.platform_fee_cents)} hint="Taken at checkout" />
        <Stat label="Owed to backers" value={money(t.commission_liability_cents)} hint={`${money(t.commission_paid_cents)} paid so far`} />
      </dl>
      {data.orders.length ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Buyer</TableHead>
              <TableHead className="max-sm:hidden">Type</TableHead>
              <TableHead className="max-sm:hidden">Status</TableHead>
              <TableHead className="text-right">Paid</TableHead>
              <TableHead className="text-right max-sm:hidden">Fee</TableHead>
              <TableHead className="text-right max-sm:hidden">Commission</TableHead>
              <TableHead className="max-sm:hidden">Date</TableHead>
              <TableHead className="sr-only">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.orders.map((o) => (
              <TableRow key={o.id}>
                <TableCell className="max-sm:whitespace-normal">
                  <span className="flex flex-col items-start gap-1">
                    {o.buyer_label}
                    <span className="sm:hidden">
                      <StatusBadge status={o.state} />
                    </span>
                  </span>
                </TableCell>
                <TableCell className="max-sm:hidden">{o.kind === "founding" ? "Founding" : `Referral · ${o.referral_code}`}</TableCell>
                <TableCell className="max-sm:hidden">
                  <StatusBadge status={o.state} />
                </TableCell>
                <TableCell className="tabular text-right">{money(o.amount_cents)}</TableCell>
                <TableCell className="tabular text-right text-muted-foreground max-sm:hidden">{money(o.platform_fee_cents)}</TableCell>
                <TableCell className="tabular text-right text-muted-foreground max-sm:hidden">{o.commission_cents ? money(o.commission_cents) : "None"}</TableCell>
                <TableCell className="text-muted-foreground max-sm:hidden">{shortDate(o.created_at)}</TableCell>
                <TableCell className="text-right">
                  {o.state === "completed" ? (
                    <ConfirmDialog
                      open={open === o.id}
                      onOpenChange={(v) => setOpen(v ? o.id : null)}
                      trigger={<Button variant="ghost" size="sm">Refund</Button>}
                      title={`Refund ${money(o.amount_cents)}?`}
                      description="This issues a full refund through PayPal, cancels any commission still on hold, and sends refund.issued to your app so access is removed."
                      confirmLabel="Refund in full"
                      destructive
                      pending={pending === o.id}
                      onConfirm={() => refund(o.id)}
                    />
                  ) : null}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <Empty className="border">
          <EmptyHeader>
            <EmptyTitle>No sales yet</EmptyTitle>
            <EmptyDescription>Share your campaign page with the people who’ve followed your build. Founding purchases show up here.</EmptyDescription>
          </EmptyHeader>
        </Empty>
      )}
    </div>
  );
}
