"use client";

import { CheckIcon, SparklesIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldLabel, FieldLegend, FieldSet } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { InputGroup, InputGroupAddon, InputGroupInput, InputGroupText } from "@/components/ui/input-group";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { useAction } from "@/hooks/use-action";
import { dollarsToCents, money, percentToBps } from "@/lib/format";
import type { Campaign, Offer, OfferSuggestion, OfferType } from "@/lib/api/types";

export const OFFER_TYPES: { value: OfferType; label: string; hint: string }[] = [
  { value: "lifetime", label: "Lifetime deal", hint: "Pay once, use it forever." },
  { value: "access_period", label: "Access for a set time", hint: "Pay once for a set number of months." },
  { value: "discount", label: "Discount coupon", hint: "Pay once to lock in a discount for life." },
  { value: "voucher", label: "Voucher or credit", hint: "Pay once for credit to spend in your product." },
  { value: "custom", label: "Something else", hint: "Describe it in the Access field." },
];

const OFFER_VALUE: Partial<Record<OfferType, { label: string; unit: string; prefix?: boolean; placeholder: string }>> = {
  access_period: { label: "Months of access", unit: "months", placeholder: "12" },
  discount: { label: "Discount for life", unit: "%", placeholder: "40" },
  voucher: { label: "Credit amount", unit: "$", prefix: true, placeholder: "75" },
};

export type Values = {
  slug: string;
  headline: string;
  summary: string;
  story: string;
  founding_price: string;
  founding_spots_cap: string;
  referral_list_price: string;
  referral_discount: string;
  commission: string;
  offer_type: OfferType;
  offer_value: string;
};

export const fromCents = (c: number) => (c / 100).toString();
export const fromBps = (b: number) => (b / 100).toString();

export function toValues(
  c: Pick<Campaign, "headline" | "summary" | "story" | "founding_price_cents" | "founding_spots_cap" | "referral_list_price_cents" | "referral_discount_bps" | "commission_bps"> & { offer?: Offer },
  slug: string,
): Values {
  const offer = c.offer ?? { type: "lifetime" as const, value: null };
  return {
    slug,
    headline: c.headline,
    summary: c.summary,
    story: c.story,
    founding_price: fromCents(c.founding_price_cents),
    founding_spots_cap: String(c.founding_spots_cap),
    referral_list_price: fromCents(c.referral_list_price_cents),
    referral_discount: fromBps(c.referral_discount_bps),
    commission: fromBps(c.commission_bps),
    offer_type: offer.type,
    offer_value: offer.value == null ? "" : offer.type === "voucher" ? fromCents(offer.value) : String(offer.value),
  };
}

export function toBody(v: Values) {
  return {
    slug: v.slug.trim().toLowerCase(),
    headline: v.headline.trim(),
    summary: v.summary.trim(),
    story: v.story.trim(),
    founding_price_cents: dollarsToCents(v.founding_price),
    founding_spots_cap: Number(v.founding_spots_cap),
    referral_list_price_cents: dollarsToCents(v.referral_list_price),
    referral_discount_bps: percentToBps(v.referral_discount),
    commission_bps: percentToBps(v.commission),
    offer_type: v.offer_type,
    offer_value: offerValue(v),
  };
}

export function offerValue(v: Pick<Values, "offer_type" | "offer_value">): number | null {
  if (!OFFER_VALUE[v.offer_type] || !v.offer_value.trim()) return null;
  return v.offer_type === "voucher" ? dollarsToCents(v.offer_value) : Math.round(Number(v.offer_value));
}

function months(n: number) {
  if (n % 12 === 0) return n === 12 ? "1 year" : `${n / 12} years`;
  return n === 1 ? "1 month" : `${n} months`;
}

/** What one payment buys, in a phrase that completes "pay once for ___". */
export function rewardPhrase(type: OfferType, raw: string): string {
  const n = Number(raw);
  const has = raw.trim() !== "" && Number.isFinite(n) && n > 0;
  switch (type) {
    case "access_period":
      return has ? `${months(Math.round(n))} of access` : "a set number of months of access";
    case "discount":
      return has ? `${+n.toFixed(2)}% off for life` : "a discount for life";
    case "voucher":
      return has ? `${money(dollarsToCents(raw))} of credit` : "credit to spend in your product";
    case "custom":
      return "what you describe in Access";
    default:
      return "lifetime access";
  }
}

const PRICE_HINT: Record<OfferType, string> = {
  lifetime: "Paid once for lifetime access.",
  access_period: "Paid once for the whole period.",
  discount: "Paid once to lock in the discount. A small amount works best.",
  voucher: "Paid once for the credit. Make the credit worth more than this.",
  custom: "Paid once for what you describe in Access.",
};

type Setter = (field: keyof Values) => React.ChangeEventHandler<HTMLInputElement | HTMLTextAreaElement>;

/** The whole offer: what one payment buys, what founding backers pay, and how referrals work. */
export function OfferFields({
  values,
  set,
  onOfferChange,
  feeBps,
  disabled,
}: {
  values: Values;
  set: Setter;
  onOfferChange: (next: { offer_type: OfferType; offer_value: string }) => void;
  feeBps: number;
  disabled?: boolean;
}) {
  const reward = rewardPhrase(values.offer_type, values.offer_value);
  const spots = Number(values.founding_spots_cap);
  return (
    <>
      <OfferPicker type={values.offer_type} value={values.offer_value} disabled={disabled} onChange={onOfferChange} />
      <FieldSet>
        <FieldLegend variant="label">Founding backers</FieldLegend>
        <FieldDescription>
          {Number.isInteger(spots) && spots > 0 ? `The first ${spots.toLocaleString()} backers` : "Founding backers"} pay once for {reward}, plus a numbered badge and a referral
          link.
        </FieldDescription>
        <div className="grid gap-3 sm:grid-cols-2">
          <MoneyField id="founding_price" label="Price" value={values.founding_price} onChange={set("founding_price")} disabled={disabled} hint={PRICE_HINT[values.offer_type]} />
          <Field>
            <FieldLabel htmlFor="founding_spots_cap">Spots</FieldLabel>
            <Input id="founding_spots_cap" type="number" min={1} max={10000} value={values.founding_spots_cap} onChange={set("founding_spots_cap")} required disabled={disabled} />
          </Field>
        </div>
      </FieldSet>
      <FieldSet>
        <FieldLegend variant="label">Friends they refer</FieldLegend>
        <FieldDescription>Friends get the same thing through a backer’s link. They pay your regular price minus their discount, and the backer earns a share.</FieldDescription>
        <div className="grid gap-3 sm:grid-cols-3">
          <MoneyField id="referral_list_price" label="Regular price" value={values.referral_list_price} onChange={set("referral_list_price")} disabled={disabled} />
          <PercentField id="referral_discount" label="Friend’s discount" value={values.referral_discount} onChange={set("referral_discount")} disabled={disabled} />
          <PercentField id="commission" label="Backer’s share" value={values.commission} onChange={set("commission")} disabled={disabled} />
        </div>
      </FieldSet>
      <OfferSummary
        reward={reward}
        foundingCents={dollarsToCents(values.founding_price)}
        spots={spots}
        listCents={dollarsToCents(values.referral_list_price)}
        discountBps={percentToBps(values.referral_discount)}
        commissionBps={percentToBps(values.commission)}
        feeBps={feeBps}
      />
    </>
  );
}

export function OfferPicker({
  type,
  value,
  onChange,
  disabled,
}: {
  type: OfferType;
  value: string;
  onChange: (next: { offer_type: OfferType; offer_value: string }) => void;
  disabled?: boolean;
}) {
  const meta = OFFER_VALUE[type];
  const hint = OFFER_TYPES.find((o) => o.value === type)?.hint;
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Field>
        <FieldLabel htmlFor="offer_type">What backers get</FieldLabel>
        <Select
          items={OFFER_TYPES}
          value={type}
          disabled={disabled}
          onValueChange={(t) => t && onChange({ offer_type: t as OfferType, offer_value: t === type ? value : "" })}
        >
          <SelectTrigger id="offer_type" className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {OFFER_TYPES.map((o) => (
                <SelectItem key={o.value} value={o.value}>
                  {o.label}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
        <FieldDescription>{hint}</FieldDescription>
      </Field>
      {meta ? (
        <Field>
          <FieldLabel htmlFor="offer_value">{meta.label}</FieldLabel>
          <InputGroup>
            {meta.prefix ? (
              <InputGroupAddon>
                <InputGroupText>{meta.unit}</InputGroupText>
              </InputGroupAddon>
            ) : null}
            <InputGroupInput
              id="offer_value"
              inputMode="decimal"
              required
              placeholder={meta.placeholder}
              value={value}
              disabled={disabled}
              onChange={(e) => onChange({ offer_type: type, offer_value: e.target.value })}
            />
            {!meta.prefix ? (
              <InputGroupAddon align="inline-end">
                <InputGroupText>{meta.unit}</InputGroupText>
              </InputGroupAddon>
            ) : null}
          </InputGroup>
        </Field>
      ) : null}
    </div>
  );
}

export const STORY_MAX = 4000;

export function OfferAdvisor({ listCents, request, onApply }: { listCents: number; request: () => Promise<OfferSuggestion>; onApply: (o: OfferSuggestion) => void }) {
  const hasListPrice = Number.isFinite(listCents) && listCents > 100;
  const [idea, setIdea] = useState<OfferSuggestion | null>(null);
  const { pending, run } = useAction();

  async function suggest() {
    const res = await run("suggest", request);
    if (res) setIdea(res);
  }

  if (!idea) {
    return (
      <div className="flex flex-col gap-3 rounded-lg border border-dashed p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-medium">Not sure what to charge?</span>
          <span className="text-sm text-muted-foreground">
            {hasListPrice
              ? "The offer advisor suggests a price, spots, friend’s discount and backer’s share around your regular price."
              : "Enter your regular price below, and the offer advisor suggests the rest around it."}
          </span>
        </div>
        <Button type="button" variant="outline" className="shrink-0" onClick={suggest} disabled={!hasListPrice || pending === "suggest"}>
          {pending === "suggest" ? <Spinner data-icon="inline-start" /> : <SparklesIcon data-icon="inline-start" />}
          Suggest an offer
        </Button>
      </div>
    );
  }

  const p = idea.projection;
  const rows: [string, string, string][] = [
    ["Price", money(idea.founding_price_cents), idea.reasons.founding_price],
    ["Spots", String(idea.founding_spots_cap), idea.reasons.spots],
    ["Friend’s discount", pct(idea.referral_discount_bps), idea.reasons.discount],
    ["Backer’s share", pct(idea.commission_bps), idea.reasons.commission],
  ];

  return (
    <div className="flex flex-col gap-4 rounded-lg bg-muted p-4">
      <div className="flex flex-wrap items-center gap-2 text-sm font-medium">
        <SparklesIcon className="size-4" />
        Suggested offer
        <Badge variant="outline">{idea.source === "ai" ? "AI" : "Template"}</Badge>
        <span className="font-normal text-muted-foreground">for your {money(idea.referral_list_price_cents)} regular price</span>
      </div>
      <dl className="flex flex-col divide-y divide-border rounded-md border bg-background text-sm">
        {rows.map(([label, value, reason]) => (
          <div key={label} className="grid gap-x-4 gap-y-0.5 px-3 py-2 sm:grid-cols-[9rem_5rem_1fr]">
            <dt className="text-muted-foreground">{label}</dt>
            <dd className="tabular">{value}</dd>
            <dd className="text-muted-foreground">{reason}</dd>
          </div>
        ))}
      </dl>
      <p className="text-sm">
        If all {idea.founding_spots_cap} spots sell you keep <span className="tabular">{money(p.all_spots_keep_cents)}</span>. If each backer brings one friend, you keep{" "}
        <span className="tabular">{money(p.one_friend_each_keep_cents)}</span> and backers earn <span className="tabular">{money(p.one_friend_each_backers_cents)}</span>.
      </p>
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          onClick={() => {
            onApply(idea);
            toast.success("Offer applied. Review it, then save.");
          }}
        >
          <CheckIcon data-icon="inline-start" />
          Apply
        </Button>
        <Button type="button" variant="ghost" onClick={suggest} disabled={pending === "suggest"}>
          {pending === "suggest" ? <Spinner data-icon="inline-start" /> : null}
          Try again
        </Button>
        <Button type="button" variant="ghost" onClick={() => setIdea(null)}>
          Dismiss
        </Button>
      </div>
    </div>
  );
}

const applyBps = (cents: number, bps: number) => Math.round((cents * bps) / 10000);

export const pct = (bps: number) => `${+(bps / 100).toFixed(2)}%`;

function OfferSummary({
  reward,
  foundingCents,
  spots,
  listCents,
  discountBps,
  commissionBps,
  feeBps,
}: {
  reward: string;
  foundingCents: number;
  spots: number;
  listCents: number;
  discountBps: number;
  commissionBps: number;
  feeBps: number;
}) {
  const founding = Number.isFinite(foundingCents) && foundingCents > 0;
  const referral = [listCents, discountBps, commissionBps].every(Number.isFinite) && listCents > 0;
  if (!founding && !referral) return null;
  const paid = listCents - applyBps(listCents, discountBps);
  const share = applyBps(paid, commissionBps);
  const kept = paid - share - applyBps(paid, feeBps);
  return (
    <div className="flex flex-col gap-1.5 rounded-2xl bg-accent/70 px-4 py-3 text-sm text-pretty text-accent-foreground">
      <p className="font-medium">In short</p>
      {founding ? (
        <p>
          Founding backers pay <span className="tabular font-medium">{money(foundingCents)}</span> once for {reward}
          {Number.isInteger(spots) && spots > 0 ? <>, while <span className="tabular">{spots.toLocaleString()}</span> spots last</> : null}.
        </p>
      ) : null}
      {referral ? (
        <p>
          A friend they refer pays <span className="tabular font-medium">{money(paid)}</span> for the same thing. Their backer earns{" "}
          <span className="tabular font-medium">{money(share)}</span>, and you keep <span className="tabular font-medium">{money(kept)}</span> after BackIt’s{" "}
          {pct(feeBps)} fee, before PayPal fees.
        </p>
      ) : null}
    </div>
  );
}

export function MoneyField({ id, label, hint, ...props }: { id: string; label: string; hint?: string; value: string; onChange: React.ChangeEventHandler<HTMLInputElement>; disabled?: boolean }) {
  return (
    <Field>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <InputGroup>
        <InputGroupAddon>
          <InputGroupText>$</InputGroupText>
        </InputGroupAddon>
        <InputGroupInput id={id} inputMode="decimal" required {...props} />
      </InputGroup>
      {hint ? <FieldDescription>{hint}</FieldDescription> : null}
    </Field>
  );
}

export function PercentField({ id, label, ...props }: { id: string; label: string; value: string; onChange: React.ChangeEventHandler<HTMLInputElement>; disabled?: boolean }) {
  return (
    <Field>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <InputGroup>
        <InputGroupInput id={id} inputMode="decimal" required {...props} />
        <InputGroupAddon align="inline-end">
          <InputGroupText>%</InputGroupText>
        </InputGroupAddon>
      </InputGroup>
    </Field>
  );
}

