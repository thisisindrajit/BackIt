"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";
import { CheckIcon, CircleCheckIcon, ClockIcon, KeyRoundIcon, RefreshCwIcon, Share2Icon, ShieldCheckIcon, TagIcon, WalletIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { ErrorState } from "@/components/backit/error-state";
import { Confetti } from "@/components/backit/confetti";
import { FoundingSeal, ReferralSeal } from "@/components/backit/founding-seal";
import { StatusBadge } from "@/components/backit/status-badge";
import { AccessCode } from "@/components/backer/access-code";
import { CopyField } from "@/components/builder/secret-reveal";
import { authedApi, useApi } from "@/hooks/use-api";
import { useAction } from "@/hooks/use-action";
import { useConfig } from "@/hooks/use-config";
import { money } from "@/lib/format";
import type { Order } from "@/lib/api/types";
import { PayPalButton } from "./paypal-button";

const accessCopy: Record<Order["access"]["status"], string> = {
  pending: "Letting the product know about your purchase…",
  delivered: "The product has your purchase. Redeem the code there to unlock your plan.",
  failed: "The product hasn't confirmed yet. BackIt keeps retrying, and your code works either way.",
  not_configured: "Redeem the code in the product to unlock your plan.",
};

export function Checkout({ orderId, approved = false }: { orderId: string; approved?: boolean }) {
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

  // Buyer came back from PayPal's full-page approval: capture once, then drop the flag from the URL.
  const autoCaptured = useRef(false);
  const shouldAutoCapture = approved && order?.state === "created";
  useEffect(() => {
    if (!shouldAutoCapture || autoCaptured.current) return;
    autoCaptured.current = true;
    router.replace(`/checkout/${orderId}`);
    void capture();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shouldAutoCapture]);

  async function cancel() {
    const o = await run("cancel", () => authedApi<Order>(`/orders/${orderId}/cancel`, { method: "POST" }));
    if (o) router.push(`/${o.campaign_slug}`);
  }

  if (error) return <ErrorState error={error} onRetry={reload} />;
  if ((loading && !order) || !order || !config) return <Skeleton className="h-80" />;

  if (order.state === "completed" || order.state === "pending_provider") {
    return <Success order={order} />;
  }

  if (order.state !== "created") {
    return (
      <Card className="mx-auto w-full max-w-xl rounded-3xl">
        <CardHeader>
          <CardTitle className="font-display text-3xl">This order is {order.state === "refunded" ? "refunded" : "no longer active"}</CardTitle>
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

  const founding = order.kind === "founding";
  const heldUntil = order.reservation_expires_at
    ? new Date(order.reservation_expires_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })
    : null;

  return (
    <div className="grid gap-8 md:grid-cols-[minmax(0,1fr)_22rem] md:items-start md:gap-12">
      <section className="stagger flex flex-col gap-8 md:pt-6">
        <div className="flex items-start gap-5">
          {founding ? (
            <FoundingSeal size={88} className="-rotate-6 max-sm:hidden" />
          ) : (
            <ReferralSeal size={88} className="-rotate-6 max-sm:hidden" />
          )}
          <div className="flex flex-col gap-2">
            <h1 className="font-display text-4xl leading-[1.05] text-balance md:text-5xl">
              {founding ? (
                <>
                  Back <em>{order.product_name}</em> early
                </>
              ) : (
                <>
                  <em>{order.product_name}</em>, for less
                </>
              )}
            </h1>
            <p className="text-muted-foreground">
              {order.builder_name ? `Built by ${order.builder_name}. ` : null}
              {founding
                ? "You’re claiming a numbered founding spot. Your seal number is set when payment clears."
                : "A founding backer sent you here, so the referral discount is already applied."}
            </p>
          </div>
        </div>

        <div className="rounded-2xl bg-secondary/45 p-5">
          <p className="text-sm font-medium">What you get</p>
          <p className="mt-1.5 text-sm leading-relaxed text-pretty text-foreground/80">{order.access_terms}</p>
        </div>

        <ul className="flex flex-col gap-4 text-sm">
          <Step icon={<WalletIcon />} title="Pay with PayPal">
            {config.paypal_mode === "sandbox" ? "A PayPal window opens to approve the payment." : "Approve the simulated payment below."}
          </Step>
          <Step icon={<KeyRoundIcon />} title="Get your access code">
            Enter it in {order.product_name} to unlock your plan.
          </Step>
          <Step icon={<Share2Icon />} title="Share your own link">
            Earn {money(order.referral_reward_cents)} each time someone buys through it.
          </Step>
        </ul>
      </section>

      <Card className="rise rounded-3xl shadow-lift md:sticky md:top-8">
        <CardHeader>
          <CardTitle className="text-base">Order summary</CardTitle>
          <CardDescription>{founding ? "Founding backer spot" : "Referral purchase"}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-5">
          <dl className="grid grid-cols-[1fr_auto] gap-y-2.5 text-sm">
            <dt className="text-muted-foreground">{order.product_name}</dt>
            <dd className="tabular text-right">{money(order.list_price_cents)}</dd>
            {order.discount_cents ? (
              <>
                <dt className="flex items-center gap-1.5 text-primary-deep">
                  <TagIcon className="size-3.5" aria-hidden />
                  Referral discount
                </dt>
                <dd className="tabular text-right text-primary-deep">−{money(order.discount_cents)}</dd>
              </>
            ) : null}
            <dt className="mt-2 self-end border-t pt-4 font-medium">You pay</dt>
            <dd className="tabular mt-2 border-t pt-3 text-right font-display text-4xl leading-none">{money(order.amount_cents)}</dd>
          </dl>
          {heldUntil ? (
            <p className="flex items-center gap-2 rounded-xl bg-accent px-3 py-2 text-xs text-accent-foreground">
              <ClockIcon className="size-3.5 shrink-0" aria-hidden />
              Your spot is held until {heldUntil}.
            </p>
          ) : null}
        </CardContent>
        <CardFooter className="flex flex-col items-stretch gap-3">
          {config.paypal_mode === "sandbox" && config.paypal_client_id && order.paypal_order_id ? (
            <PayPalButton clientId={config.paypal_client_id} paypalOrderId={order.paypal_order_id} approveUrl={order.approve_url} onApprove={capture} disabled={pending !== null} />
          ) : (
            <Button size="lg" onClick={capture} disabled={pending !== null}>
              {pending === "capture" ? <Spinner data-icon="inline-start" /> : null}
              Approve sandbox payment
            </Button>
          )}
          <p className="flex items-center justify-center gap-1.5 text-center text-xs text-muted-foreground">
            <ShieldCheckIcon className="size-3.5" aria-hidden />
            {config.paypal_mode === "sandbox" ? "PayPal sandbox. No real money moves." : "Simulated approval. No PayPal window opens."}
          </p>
          <Button variant="ghost" size="sm" onClick={cancel} disabled={pending !== null}>
            {pending === "cancel" ? <Spinner data-icon="inline-start" /> : null}
            Cancel order
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}

function Step({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-3">
      <span className="grid size-8 shrink-0 place-items-center rounded-full bg-primary/15 text-primary-deep [&_svg]:size-4" aria-hidden>
        {icon}
      </span>
      <span className="flex flex-col gap-0.5 pt-1">
        <span className="font-medium">{title}</span>
        <span className="text-muted-foreground">{children}</span>
      </span>
    </li>
  );
}

const accessIcon: Record<Order["access"]["status"], React.ReactNode> = {
  pending: <Spinner className="size-4" />,
  delivered: <CircleCheckIcon className="size-4 text-primary" aria-hidden />,
  failed: <RefreshCwIcon className="size-4 text-muted-foreground" aria-hidden />,
  not_configured: <KeyRoundIcon className="size-4 text-muted-foreground" aria-hidden />,
};

function Success({ order }: { order: Order }) {
  const b = order.backing;
  const done = order.state === "completed";
  const canShare = typeof navigator !== "undefined" && "share" in navigator;
  const shareText = `I’m backing ${order.product_name} on BackIt. Use my link for a discount:`;

  return (
    <div className="mx-auto flex w-full max-w-xl flex-col gap-8">
      {done ? <Confetti id={order.id} /> : null}
      <header className="flex flex-col items-center gap-5 pt-2 text-center">
        {b?.badge_number ? (
          <div className="pop-in">
            <FoundingSeal number={b.badge_number} size={168} />
          </div>
        ) : b && order.kind === "referral" ? (
          <div className="pop-in">
            <ReferralSeal size={140} />
          </div>
        ) : (
          <span className="pop-in grid size-20 place-items-center rounded-full bg-primary text-white">
            {done ? <CheckIcon className="size-9" /> : <Spinner className="size-7" />}
          </span>
        )}
        <div className="rise flex flex-col gap-2" style={{ animationDelay: "180ms" }}>
          <h1 className="font-display text-4xl leading-[1.05] text-balance md:text-5xl">
            {!done ? (
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
          </h1>
          <p className="text-muted-foreground">
            {done
              ? `Paid ${money(order.amount_cents)} for ${order.product_name}${order.builder_name ? ` by ${order.builder_name}` : ""}.`
              : "PayPal is still processing this payment. This page updates on its own."}
          </p>
        </div>
      </header>

      {b ? (
        <Card className="rise rounded-3xl shadow-lift" style={{ animationDelay: "300ms" }}>
          <CardContent className="flex flex-col gap-6">
            <AccessCode code={b.claim_code} productName={order.product_name} productUrl={order.product_url} />
            <p className="-mt-2 flex items-start gap-2 text-sm text-muted-foreground">
              <span className="mt-0.5 shrink-0">{accessIcon[order.access.status]}</span>
              {accessCopy[order.access.status]}
            </p>
            <Separator />
            <div className="flex flex-col gap-3">
              <div className="flex flex-col gap-1">
                <p className="font-display text-2xl leading-tight">
                  Earn <em>{money(order.referral_reward_cents)}</em> per friend
                </p>
                <p className="text-sm text-muted-foreground">
                  Share your link with people who’d use {order.product_name}. They get a discount, and you earn on every sale once its refund window closes.
                </p>
              </div>
              <CopyField value={b.share_url} label="Referral link" />
              <div className="flex flex-wrap gap-2">
                {canShare ? (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void navigator.share({ title: order.product_name, text: shareText, url: b.share_url }).catch(() => {})}
                  >
                    <Share2Icon data-icon="inline-start" />
                    Share
                  </Button>
                ) : null}
                <Button
                  variant="outline"
                  size="sm"
                  render={<a href={`https://x.com/intent/post?text=${encodeURIComponent(shareText)}&url=${encodeURIComponent(b.share_url)}`} target="_blank" rel="noreferrer" />}
                  nativeButton={false}
                >
                  Post on X
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  render={<a href={`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(b.share_url)}`} target="_blank" rel="noreferrer" />}
                  nativeButton={false}
                >
                  Share on LinkedIn
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <div className="flex flex-wrap justify-center gap-2">
        <Button render={<Link href="/app/backings" />} nativeButton={false}>
          Go to your backings
        </Button>
        <Button render={<Link href={`/${order.campaign_slug}`} />} nativeButton={false} variant="ghost">
          Back to campaign
        </Button>
      </div>
    </div>
  );
}
