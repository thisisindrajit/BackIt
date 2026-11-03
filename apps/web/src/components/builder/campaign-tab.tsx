"use client";

import { CheckIcon, SparklesIcon, XIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldDescription, FieldGroup, FieldLabel, FieldLegend, FieldSet } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { InputGroup, InputGroupAddon, InputGroupInput, InputGroupText } from "@/components/ui/input-group";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { authedApi, useApi } from "@/hooks/use-api";
import { ApiError, errorMessage } from "@/lib/api/client";
import { dollarsToCents, money, percentToBps } from "@/lib/format";
import type { Campaign, CampaignDraft, Product, Readiness } from "@/lib/api/types";
import { useAction } from "@/hooks/use-action";

type Values = {
  slug: string;
  headline: string;
  summary: string;
  story: string;
  founding_price: string;
  founding_spots_cap: string;
  referral_list_price: string;
  referral_discount: string;
  commission: string;
};

const fromCents = (c: number) => (c / 100).toString();
const fromBps = (b: number) => (b / 100).toString();

function toValues(c: Pick<Campaign, "headline" | "summary" | "story" | "founding_price_cents" | "founding_spots_cap" | "referral_list_price_cents" | "referral_discount_bps" | "commission_bps">, slug: string): Values {
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
  };
}

function toBody(v: Values) {
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
  };
}

export function CampaignTab({ product, onChange }: { product: Product; onChange: () => void }) {
  const campaign = product.campaign;
  const [draft, setDraft] = useState<CampaignDraft | null>(null);

  if (!campaign && !draft) return <DraftStart product={product} onDraft={setDraft} />;

  return (
    <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_20rem]">
      <CampaignForm
        key={campaign?.id ?? "new"}
        product={product}
        campaign={campaign}
        draft={draft}
        onSaved={() => {
          setDraft(null);
          onChange();
        }}
      />
      {campaign ? <ReadinessPanel campaign={campaign} onPublished={onChange} /> : null}
    </div>
  );
}

function DraftStart({ product, onDraft }: { product: Product; onDraft: (d: CampaignDraft) => void }) {
  const [text, setText] = useState(product.description);
  const { pending, run } = useAction();

  async function generate() {
    const d = await run("draft", () =>
      authedApi<CampaignDraft>(`/products/${product.id}/campaign-draft`, { method: "POST", body: { source_text: text || null } }),
    );
    if (d) onDraft(d);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Draft your campaign</CardTitle>
        <CardDescription>
          The AI writes your story from what you share here. Next, you’ll review it and set the offer: founding price, number of spots, buyer
          discount, and backer commission. Nothing is saved or published until you do.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="source_text">About your product</FieldLabel>
            <Textarea id="source_text" rows={6} maxLength={8000} value={text} onChange={(e) => setText(e.target.value)} />
            <FieldDescription>Paste your landing page copy, changelog highlights, or who it’s for. It won’t invent revenue or users.</FieldDescription>
          </Field>
          <Button onClick={generate} className="self-start" disabled={pending === "draft"}>
            {pending === "draft" ? <Spinner data-icon="inline-start" /> : <SparklesIcon data-icon="inline-start" />}
            Draft campaign
          </Button>
        </FieldGroup>
      </CardContent>
    </Card>
  );
}

function CampaignForm({ product, campaign, draft, onSaved }: { product: Product; campaign: Campaign | null; draft: CampaignDraft | null; onSaved: () => void }) {
  const feeBps = product.campaign?.platform_fee_bps ?? 800;
  const [values, setValues] = useState<Values>(() =>
    campaign ? toValues(campaign, campaign.slug) : toValues(draft!, product.slug),
  );
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const locked = campaign?.status === "published";
  const set = (k: keyof Values) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setValues((v) => ({ ...v, [k]: e.target.value }));

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      const body = toBody(values);
      if (campaign) {
        const patch = locked ? { headline: body.headline, summary: body.summary, story: body.story } : body;
        await authedApi(`/campaigns/${campaign.id}`, { method: "PATCH", body: patch });
      } else {
        await authedApi(`/campaigns`, { method: "POST", body: { product_id: product.id, ...body } });
      }
      toast.success(campaign ? "Campaign saved" : "Campaign created as a draft");
      onSaved();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setPending(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{campaign ? "Campaign" : "Review the draft"}</CardTitle>
        <CardDescription>
          {locked ? "Prices are locked while the campaign is live. Copy can still change." : "Everything here is editable. Backers only see it after you publish."}
        </CardDescription>
        {draft ? (
          <CardAction>
            <Badge variant="secondary">{draft.source === "ai" ? "AI draft" : "Template draft"}</Badge>
          </CardAction>
        ) : null}
      </CardHeader>
      <CardContent>
        <form onSubmit={save}>
          <FieldGroup>
            {draft?.missing_evidence.length ? (
              <Alert className="border-transparent bg-accent text-accent-foreground">
                <AlertTitle>Worth adding before you publish</AlertTitle>
                <AlertDescription className="text-accent-foreground/80">
                  <ul className="list-disc pl-4">
                    {draft.missing_evidence.map((m) => (
                      <li key={m}>{m}</li>
                    ))}
                  </ul>
                </AlertDescription>
              </Alert>
            ) : null}
            {error ? (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}
            <Field>
              <FieldLabel htmlFor="slug">Page address</FieldLabel>
              <InputGroup>
                <InputGroupAddon>
                  <InputGroupText>backit.club/</InputGroupText>
                </InputGroupAddon>
                <InputGroupInput id="slug" value={values.slug} onChange={set("slug")} required pattern="[a-z0-9][a-z0-9\-]{1,38}[a-z0-9]" disabled={locked} />
              </InputGroup>
            </Field>
            <Field>
              <FieldLabel htmlFor="headline">Headline</FieldLabel>
              <Input id="headline" value={values.headline} onChange={set("headline")} required maxLength={160} />
            </Field>
            <Field>
              <FieldLabel htmlFor="summary">Summary</FieldLabel>
              <Textarea id="summary" rows={2} value={values.summary} onChange={set("summary")} required maxLength={1000} />
            </Field>
            <Field>
              <FieldLabel htmlFor="story">Story</FieldLabel>
              <Textarea id="story" rows={12} value={values.story} onChange={set("story")} required maxLength={STORY_MAX} className="min-h-64" />
              <FieldDescription className="flex flex-wrap justify-between gap-x-4 gap-y-1">
                <span>Why you’re building this, who it’s for, and what backers help unlock. Markdown supported: ## headings, **bold**, lists, links.</span>
                <span className="tabular shrink-0">
                  {values.story.length.toLocaleString()}/{STORY_MAX.toLocaleString()}
                </span>
              </FieldDescription>
            </Field>
            <FieldSet>
              <FieldLegend>Founding offer</FieldLegend>
              <FieldDescription>Founding backers pay once, get a permanent numbered badge, and a referral link.</FieldDescription>
              <div className="grid gap-3 sm:grid-cols-2">
                <MoneyField id="founding_price" label="Price" value={values.founding_price} onChange={set("founding_price")} disabled={locked} />
                <Field>
                  <FieldLabel htmlFor="founding_spots_cap">Spots</FieldLabel>
                  <Input id="founding_spots_cap" type="number" min={1} max={10000} value={values.founding_spots_cap} onChange={set("founding_spots_cap")} required disabled={locked} />
                </Field>
              </div>
            </FieldSet>
            <FieldSet>
              <FieldLegend>Referral offer</FieldLegend>
              <FieldDescription>What people pay through a backer’s link, and what that backer earns.</FieldDescription>
              <div className="grid gap-3 sm:grid-cols-3">
                <MoneyField id="referral_list_price" label="List price" value={values.referral_list_price} onChange={set("referral_list_price")} disabled={locked} />
                <PercentField id="referral_discount" label="Buyer discount" value={values.referral_discount} onChange={set("referral_discount")} disabled={locked} />
                <PercentField id="commission" label="Backer commission" value={values.commission} onChange={set("commission")} disabled={locked} />
              </div>
              <FieldDescription>Commission is paid on what the buyer actually pays. BackIt’s {feeBps / 100}% fee comes out of each sale.</FieldDescription>
              <ReferralExample
                listCents={dollarsToCents(values.referral_list_price)}
                discountBps={percentToBps(values.referral_discount)}
                commissionBps={percentToBps(values.commission)}
                feeBps={feeBps}
              />
            </FieldSet>
            {draft?.disclosure ? <p className="text-sm text-muted-foreground">{draft.disclosure}</p> : null}
            <Button type="submit" className="self-start" disabled={pending}>
              {pending ? <Spinner data-icon="inline-start" /> : null}
              {campaign ? "Save changes" : "Save as draft"}
            </Button>
          </FieldGroup>
        </form>
      </CardContent>
    </Card>
  );
}

const STORY_MAX = 4000;

const applyBps = (cents: number, bps: number) => Math.round((cents * bps) / 10000);

const pct = (bps: number) => `${+(bps / 100).toFixed(2)}%`;

function ReferralExample({ listCents, discountBps, commissionBps, feeBps }: { listCents: number; discountBps: number; commissionBps: number; feeBps: number }) {
  if (![listCents, discountBps, commissionBps].every(Number.isFinite) || listCents <= 0) return null;
  const paid = listCents - applyBps(listCents, discountBps);
  const reward = applyBps(paid, commissionBps);
  const fee = applyBps(paid, feeBps);
  const kept = paid - reward - fee;
  return (
    <div className="flex flex-col gap-1.5 rounded-2xl bg-accent/70 px-4 py-3 text-sm text-accent-foreground">
      <p className="font-medium">Example</p>
      <ul className="tabular flex flex-wrap gap-1.5 text-xs">
        <li className="rounded-full bg-background/70 px-2.5 py-1">List price {money(listCents)}</li>
        <li className="rounded-full bg-background/70 px-2.5 py-1">Buyer discount {pct(discountBps)}</li>
        <li className="rounded-full bg-background/70 px-2.5 py-1">Backer commission {pct(commissionBps)}</li>
        <li className="rounded-full bg-background/70 px-2.5 py-1">BackIt fee {pct(feeBps)}</li>
      </ul>
      <p className="text-pretty">
        A friend uses a backer’s link and pays <span className="tabular font-medium">{money(paid)}</span> instead of{" "}
        <span className="tabular">{money(listCents)}</span>. The backer earns <span className="tabular font-medium">{money(reward)}</span>{" "}
        <span className="tabular">({pct(commissionBps)} of {money(paid)})</span>, BackIt takes <span className="tabular">{money(fee)}</span>{" "}
        <span className="tabular">({pct(feeBps)} of {money(paid)})</span>, and you keep <span className="tabular font-medium">{money(kept)}</span> before PayPal fees.
      </p>
    </div>
  );
}

function MoneyField({ id, label, ...props }: { id: string; label: string; value: string; onChange: React.ChangeEventHandler<HTMLInputElement>; disabled?: boolean }) {
  return (
    <Field>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <InputGroup>
        <InputGroupAddon>
          <InputGroupText>$</InputGroupText>
        </InputGroupAddon>
        <InputGroupInput id={id} inputMode="decimal" required {...props} />
      </InputGroup>
    </Field>
  );
}

function PercentField({ id, label, ...props }: { id: string; label: string; value: string; onChange: React.ChangeEventHandler<HTMLInputElement>; disabled?: boolean }) {
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

function ReadinessPanel({ campaign, onPublished }: { campaign: Campaign; onPublished: () => void }) {
  const { data: readiness, reload: load } = useApi<Readiness>(campaign.status === "published" ? null : `/campaigns/${campaign.id}/readiness`);
  const { pending, run } = useAction();

  const seen = useRef(campaign.updated_at);
  useEffect(() => {
    if (seen.current === campaign.updated_at) return;
    seen.current = campaign.updated_at;
    void load();
  }, [load, campaign.updated_at]);

  async function publish() {
    try {
      await run("publish", async () => {
        try {
          return await authedApi(`/campaigns/${campaign.id}/publish`, { method: "POST" });
        } catch (e) {
          if (e instanceof ApiError && e.code === "not_ready") load();
          throw e;
        }
      }, "Campaign is live");
      onPublished();
    } catch {}
  }

  if (campaign.status === "published") {
    return (
      <Card size="sm" className="h-fit xl:sticky xl:top-6">
        <CardHeader>
          <CardTitle>Live</CardTitle>
          <CardDescription>
            {campaign.founding_spots_taken} of {campaign.founding_spots_cap} founding spots taken.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card size="sm" className="h-fit xl:sticky xl:top-6">
      <CardHeader>
        <CardTitle>Ready to publish?</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <ul className="flex flex-col gap-2.5">
          {readiness?.checks.map((c) => (
            <li key={c.key} className="flex gap-2 text-sm">
              {c.ok ? <CheckIcon className="mt-0.5 size-4 shrink-0 text-success" aria-label="Done" /> : <XIcon className="mt-0.5 size-4 shrink-0 text-destructive" aria-label="Not done" />}
              <span className="flex flex-col">
                <span>{c.label}</span>
                {!c.ok && c.detail ? <span className="text-muted-foreground">{c.detail}</span> : null}
              </span>
            </li>
          )) ??
            [0, 1, 2, 3].map((i) => (
              <li key={i} className="flex gap-2" aria-hidden>
                <Skeleton className="size-4 shrink-0 rounded-full" />
                <Skeleton className="h-4 flex-1" />
              </li>
            ))}
        </ul>
        <Button onClick={publish} disabled={!readiness?.ready || pending === "publish"}>
          {pending === "publish" ? <Spinner data-icon="inline-start" /> : null}
          Publish campaign
        </Button>
      </CardContent>
    </Card>
  );
}
