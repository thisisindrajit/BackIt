"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";
import { CheckIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { ErrorState } from "@/components/backit/error-state";
import { Confetti } from "@/components/backit/confetti";
import { FoundingSeal } from "@/components/backit/founding-seal";
import { StatusBadge } from "@/components/backit/status-badge";
import { CopyField } from "@/components/builder/secret-reveal";
import { authedApi, useApi } from "@/hooks/use-api";
import { useAction } from "@/hooks/use-action";
import { useConfig } from "@/hooks/use-config";
import { money } from "@/lib/format";
import type { Order } from "@/lib/api/types";
import { PayPalButton } from "./paypal-button";

const accessCopy: Record<Order["access"]["status"], string> = {
  pending: "Unlocking your access in the product…",
  delivered: "Access unlocked in the product.",
  failed: "The product hasn't confirmed access yet. BackIt keeps retrying, and the builder can see it.",
  not_configured: "The builder will grant access directly.",
};

export function Checkout({ orderId }: { orderId: string }) {
  const router = useRouter();
  const config = useConfig();
  const { data: order, setData, error, loading, reload } = useApi<Order>(`/orders/${orderId}`);
  const { pending, run } = useAction();
  const polls = useRef(0);

  const waiting = order && (order.state === "pending_provider" || (order.state === "completed" && order.access.status === "pending"));
  useEffect(() => {
    if (!waiting || polls.current > 15) return;
    const t = setTimeout(() => {
      polls.current += 1;
      void reload();
    }, 2000);
    return () => clearTimeout(t);
  }, [waiting, order, reload]);

  async function capture() {
    const o = await run("capture", () => authedApi<Order>(`/orders/${orderId}/capture`, { method: "POST", idempotencyKey: `capture-${orderId}` }));
    if (o) setData(o);
  }

  async function cancel() {
    const o = await run("cancel", () => authedApi<Order>(`/orders/${orderId}/cancel`, { method: "POST" }));
    if (o) router.push(`/${o.campaign_slug}`);
  }

  if (error) return <ErrorState error={error} onRetry={reload} />;
  if ((loading && !order) || !order || !config) return <Skeleton className="h-80" />;

  if (order.state === "completed" || order.state === "pending_provider") {
    const b = order.backing;
    return (
      <Card className="rounded-3xl shadow-lift">
        <CardHeader className="items-center text-center">
          <div className="relative mb-2 grid place-items-center py-2">
            {order.state === "completed" ? <Confetti /> : null}
            {b?.badge_number ? (
              <div className="pop-in">
                <FoundingSeal number={b.badge_number} size={148} />
              </div>
            ) : (
              <span className="pop-in grid size-16 place-items-center rounded-full bg-primary text-white">
                {order.state === "pending_provider" ? <Spinner className="size-6" /> : <CheckIcon className="size-7" />}
              </span>
            )}
          </div>
          <CardTitle className="font-display text-4xl leading-tight">
            {order.state === "pending_provider" ? (
              "Confirming with PayPal"
            ) : b?.badge_number ? (
              <>
                You’re founding backer <em>#{b.badge_number}</em>
              </>
            ) : (
              <>
                You’re <em>in</em>
              </>
            )}
          </CardTitle>
          <CardDescription className="text-base">
            {order.state === "pending_provider" ? "PayPal is still processing this payment. This page updates on its own." : `Paid ${money(order.amount_cents)}.`}
          </CardDescription>
        </CardHeader>
        {b ? (
          <CardContent className="flex flex-col gap-6">
            <div className="flex flex-col gap-2">
              <p className="text-sm font-medium">Your referral link</p>
              <CopyField value={b.share_url} label="Referral link" />
              <p className="text-xs text-muted-foreground">Share it with people who’d use the product. They get a discount and you earn a commission on each sale.</p>
            </div>
            <Separator />
            <p className="flex items-center gap-2 text-sm">
              {order.access.status === "pending" ? <Spinner /> : null}
              {accessCopy[order.access.status]}
            </p>
          </CardContent>
        ) : null}
        <CardFooter className="flex flex-wrap gap-2">
          <Button render={<Link href="/app/backings" />} nativeButton={false}>
            Go to your backings
          </Button>
          <Button render={<Link href={`/${order.campaign_slug}`} />} nativeButton={false} variant="ghost">
            Back to campaign
          </Button>
        </CardFooter>
      </Card>
    );
  }

  if (order.state !== "created") {
    return (
      <Card>
        <CardHeader>
          <CardTitle>This order is {order.state === "refunded" ? "refunded" : "no longer active"}</CardTitle>
          <CardDescription>
            <StatusBadge status={order.state} />
          </CardDescription>
        </CardHeader>
        <CardFooter>
          <Button render={<Link href={`/${order.campaign_slug}`} />} nativeButton={false} variant="outline">
            Back to campaign
          </Button>
        </CardFooter>
      </Card>
    );
  }

  return (
    <Card className="rounded-3xl shadow-lift">
      <CardHeader>
        <CardTitle className="font-display text-3xl">{order.kind === "founding" ? "Founding backer spot" : "Referral purchase"}</CardTitle>
        <CardDescription>
          {order.reservation_expires_at
            ? `Your spot is held until ${new Date(order.reservation_expires_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}.`
            : "Review and pay with PayPal."}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-[1fr_auto] gap-y-2 text-sm">
          <dt className="text-muted-foreground">List price</dt>
          <dd className="tabular text-right">{money(order.list_price_cents)}</dd>
          {order.discount_cents ? (
            <>
              <dt className="text-muted-foreground">Referral discount</dt>
              <dd className="tabular text-right">−{money(order.discount_cents)}</dd>
            </>
          ) : null}
          <dt className="border-t pt-2 font-medium">You pay</dt>
          <dd className="tabular border-t pt-2 text-right font-heading text-2xl">{money(order.amount_cents)}</dd>
        </dl>
      </CardContent>
      <CardFooter className="flex flex-col items-stretch gap-3">
        {config.paypal_mode === "sandbox" && config.paypal_client_id && order.paypal_order_id ? (
          <PayPalButton clientId={config.paypal_client_id} paypalOrderId={order.paypal_order_id} onApprove={capture} disabled={pending !== null} />
        ) : (
          <>
            <Button size="lg" onClick={capture} disabled={pending !== null}>
              {pending === "capture" ? <Spinner data-icon="inline-start" /> : null}
              Approve sandbox payment
            </Button>
            <p className="text-center text-xs text-muted-foreground">Simulated PayPal approval. No PayPal window opens in mock mode.</p>
          </>
        )}
        <Button variant="ghost" onClick={cancel} disabled={pending !== null}>
          Cancel
        </Button>
      </CardFooter>
    </Card>
  );
}
