"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { FoundingSeal } from "@/components/backit/founding-seal";
import { Card, CardAction, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { authedApi } from "@/hooks/use-api";
import { ApiError, errorMessage } from "@/lib/api/client";
import { money, percent } from "@/lib/format";
import type { Order, PublicCampaign } from "@/lib/api/types";

type Kind = "founding" | "referral";

export function BuyPanel({ campaign: c, referralCode, signedIn }: { campaign: PublicCampaign; referralCode?: string; signedIn: boolean }) {
  const router = useRouter();
  const [pending, setPending] = useState<Kind | null>(null);
  const [owned, setOwned] = useState(false);
  const idempotencyKeys = useRef(new Map<string, string>());
  const soldOut = c.founding.spots_left <= 0;
  const ended = c.status === "closed";
  const closed = c.status !== "published" || owned;

  async function buy(kind: Kind) {
    const here = `/${c.slug}${referralCode ? `?ref=${encodeURIComponent(referralCode)}` : ""}`;
    if (!signedIn) {
      router.push(`/sign-up?next=${encodeURIComponent(here)}`);
      return;
    }
    const purchase = JSON.stringify([c.id, kind, kind === "referral" ? referralCode : null]);
    let key = idempotencyKeys.current.get(purchase);
    if (!key) {
      key = crypto.randomUUID();
      idempotencyKeys.current.set(purchase, key);
    }
    setPending(kind);
    try {
      const order = await authedApi<Order>(`/campaigns/${c.id}/orders`, {
        method: "POST",
        body: kind === "referral" ? { kind, referral_code: referralCode } : { kind },
        idempotencyKey: key,
      });
      router.push(`/checkout/${order.id}`);
    } catch (e) {
      if (e instanceof ApiError && e.code === "already_purchased") setOwned(true);
      else toast.error(errorMessage(e));
      setPending(null);
    }
  }

  const referral = referralCode ? (
    <Card className="rounded-3xl shadow-lift ring-primary/40">
      <CardHeader>
        <CardTitle className="text-xl">
          <em className="text-primary-deep">{c.referrer?.display_name}</em> sent you
        </CardTitle>
        <CardDescription>
          {percent(c.referral.discount_bps)} off {c.product.name}. {c.referrer?.display_name} earns {money(c.referral.commission_cents)} if you buy.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p className="flex items-baseline gap-2">
          <span className="tabular font-heading text-5xl">{money(c.referral.price_cents)}</span>
          <span className="text-sm text-muted-foreground">once</span>
          <span className="tabular text-muted-foreground line-through">{money(c.referral.list_price_cents)}/month</span>
        </p>
      </CardContent>
      <CardFooter>
        <Button className="w-full" size="lg" disabled={closed || pending !== null} onClick={() => buy("referral")}>
          {pending === "referral" ? <Spinner data-icon="inline-start" /> : null}
          Buy with {percent(c.referral.discount_bps)} off
        </Button>
      </CardFooter>
    </Card>
  ) : null;

  const founding = (
    <Card className="rounded-3xl shadow-lift">
      <CardHeader>
        <CardTitle className="text-xl">Founding backer</CardTitle>
        <CardDescription>
          {c.offer.label} of {c.product.name}, a numbered badge, and earn {money(c.referral.commission_cents)} for each friend who buys with your link.
        </CardDescription>
        {!soldOut && !ended ? (
          <CardAction>
            <FoundingSeal number={c.founding.spots_taken + 1} size={68} className="transition-transform duration-300 ease-(--ease-out) hover:rotate-12" />
          </CardAction>
        ) : null}
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <p className="flex items-baseline gap-2">
          <span className="tabular font-heading text-5xl">{money(c.founding.price_cents)}</span>
          <span className="text-sm text-muted-foreground">once</span>
          {!soldOut && !ended ? <span className="tabular text-sm text-muted-foreground">badge No. {c.founding.spots_taken + 1} is next</span> : null}
        </p>
        <div className="flex flex-col gap-2">
          <Progress value={(c.founding.spots_taken / Math.max(c.founding.spots_cap, 1)) * 100} aria-label="Founding spots taken" />
          <p className="tabular text-sm text-muted-foreground">
            {ended
              ? `Ended with ${c.founding.spots_taken} of ${c.founding.spots_cap} spots taken`
              : soldOut
                ? "All founding spots are taken"
                : `${c.founding.spots_left} of ${c.founding.spots_cap} spots left`}
          </p>
        </div>
      </CardContent>
      <CardFooter>
        <Button className="w-full" size="lg" variant={referralCode ? "outline" : "default"} disabled={closed || soldOut || pending !== null} onClick={() => buy("founding")}>
          {pending === "founding" ? <Spinner data-icon="inline-start" /> : null}
          {ended ? "Campaign ended" : soldOut ? "Sold out" : "Become a founding backer"}
        </Button>
      </CardFooter>
    </Card>
  );

  return (
    <div className="flex flex-col gap-4">
      {owned ? (
        <p className="rounded-2xl bg-accent px-4 py-3 text-sm text-accent-foreground">
          You already backed {c.product.name}.{" "}
          <Link href="/app/backings" className="underline underline-offset-4">
            See your backing
          </Link>
        </p>
      ) : null}
      {referral}
      {referral ? <Separator /> : null}
      {founding}
      <p className="text-xs text-muted-foreground">
        {ended ? "This campaign has ended. Backers keep their access." : owned ? "One purchase per backer." : closed ? "This campaign is closed." : "Checkout runs in PayPal sandbox. No real money moves."}
        {!signedIn && !closed ? " You'll create a free account first." : null}
      </p>
    </div>
  );
}
