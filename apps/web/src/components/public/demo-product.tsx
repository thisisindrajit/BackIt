"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ErrorState } from "@/components/backit/error-state";
import { StatusBadge } from "@/components/backit/status-badge";
import { shortDate } from "@/lib/format";

const URL = process.env.NEXT_PUBLIC_DEMO_PRODUCT_URL ?? "http://localhost:8100";

type Entitlement = { order_id: string; buyer_email: string | null; plan_id: string | null; status: "active" | "revoked"; granted_at: string; revoked_at: string | null };
type DemoEvent = { event_id: string; event_type: string; order_id: string | null; outcome: string; received_at: string };

export function DemoProduct() {
  const [data, setData] = useState<{ entitlements: Entitlement[]; events: DemoEvent[] } | null>(null);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(async () => {
    try {
      const [e, v] = await Promise.all([fetch(`${URL}/entitlements`), fetch(`${URL}/events?limit=20`)]);
      if (!e.ok || !v.ok) throw new Error("The demo product returned an error.");
      setData({ entitlements: await e.json(), events: await v.json() });
      setError(null);
    } catch {
      setError(new Error(`Can't reach the demo product at ${URL}. Start it with BACKIT_WEBHOOK_SECRET set.`));
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [load]);

  return (
    <div className="flex min-h-svh flex-col">
      <header className="border-b">
        <div className="mx-auto flex h-14 w-full max-w-4xl items-center justify-between gap-4 px-4 sm:px-6">
          <span className="font-heading font-semibold">Demo product</span>
          <span className="text-sm text-muted-foreground">Receives BackIt webhooks · updates every 3s</span>
        </div>
      </header>
      <main className="mx-auto flex w-full max-w-4xl flex-col gap-10 px-4 py-10 sm:px-6">
        <p className="max-w-prose text-muted-foreground">
          A stand-in for the builder&apos;s own app. When BackIt sends a signed <code className="font-mono text-sm">order.completed</code> webhook, access is granted here.{" "}
          <code className="font-mono text-sm">refund.issued</code> revokes it. Replays are ignored.
        </p>
        {error ? <ErrorState error={error} onRetry={load} /> : null}
        <section className="flex flex-col gap-3">
          <div className="flex items-center justify-between gap-2">
            <h1 className="text-xl font-semibold">Who has access</h1>
            <Button variant="outline" size="sm" onClick={load}>
              Refresh
            </Button>
          </div>
          {!data && !error ? (
            <Skeleton className="h-32" />
          ) : data?.entitlements.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Customer</TableHead>
                  <TableHead className="max-sm:hidden">Order</TableHead>
                  <TableHead>Access</TableHead>
                  <TableHead className="max-sm:hidden">Since</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.entitlements.map((e) => (
                  <TableRow key={e.order_id}>
                    <TableCell className="max-w-40 truncate">{e.buyer_email ?? "Unknown"}</TableCell>
                    <TableCell className="font-mono text-xs max-sm:hidden">{e.order_id}</TableCell>
                    <TableCell>
                      <StatusBadge status={e.status} />
                    </TableCell>
                    <TableCell className="text-muted-foreground max-sm:hidden">{shortDate(e.revoked_at ?? e.granted_at)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : data ? (
            <Empty className="border">
              <EmptyHeader>
                <EmptyTitle>No customers yet</EmptyTitle>
                <EmptyDescription>Buy a founding spot on a BackIt campaign and access appears here within seconds.</EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : null}
        </section>
        <section className="flex flex-col gap-3">
          <h2 className="text-xl font-semibold">Webhook log</h2>
          {data?.events.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Event</TableHead>
                  <TableHead>Outcome</TableHead>
                  <TableHead>Received</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.events.map((v) => (
                  <TableRow key={v.event_id}>
                    <TableCell className="flex flex-col">
                      <span className="font-mono text-xs">{v.event_type}</span>
                      <span className="font-mono text-xs text-muted-foreground">{v.event_id}</span>
                    </TableCell>
                    <TableCell>{v.outcome.replace(/_/g, " ")}</TableCell>
                    <TableCell className="text-muted-foreground">{new Date(v.received_at).toLocaleTimeString()}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-sm text-muted-foreground">No webhooks received yet.</p>
          )}
        </section>
      </main>
    </div>
  );
}
