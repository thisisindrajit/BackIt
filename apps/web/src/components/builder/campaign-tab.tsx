"use client";

import { CheckIcon, SparklesIcon, XIcon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldDescription, FieldGroup, FieldLabel, FieldLegend, FieldSet } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { InputGroup, InputGroupAddon, InputGroupInput, InputGroupText } from "@/components/ui/input-group";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { authedApi } from "@/hooks/use-api";
import { ApiError, errorMessage } from "@/lib/api/client";
import { dollarsToCents, percentToBps } from "@/lib/format";
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
    <div className="grid gap-6 lg:grid-cols-[1fr_18rem]">
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
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>Draft your campaign</CardTitle>
        <CardDescription>
          The AI suggests a pitch and an offer from what you share here. Nothing is saved or published until you review it.
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
              <Textarea id="story" rows={6} value={values.story} onChange={set("story")} required maxLength={10000} />
              <FieldDescription>Why you’re building this and what backers help unlock.</FieldDescription>
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
              <FieldDescription>Commission is paid on what the buyer actually pays. BackIt’s {product.campaign ? product.campaign.platform_fee_bps / 100 : 8}% fee comes out of each sale.</FieldDescription>
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
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const { pending, run } = useAction();

  const load = useCallback(() => {
    authedApi<Readiness>(`/campaigns/${campaign.id}/readiness`).then(setReadiness).catch(() => {});
  }, [campaign.id]);

  useEffect(load, [load, campaign.updated_at]);

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
      <Card size="sm" className="h-fit">
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
    <Card size="sm" className="h-fit">
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
          )) ?? <Spinner />}
        </ul>
        <Button onClick={publish} disabled={!readiness?.ready || pending === "publish"}>
          {pending === "publish" ? <Spinner data-icon="inline-start" /> : null}
          Publish campaign
        </Button>
      </CardContent>
    </Card>
  );
}
