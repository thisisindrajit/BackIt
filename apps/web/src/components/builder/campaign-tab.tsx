"use client";

import { CheckIcon, SparklesIcon, XIcon } from "lucide-react";
import { useState } from "react";
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
import { dollarsToCents, shortDate } from "@/lib/format";
import type { Campaign, CampaignDraft, OfferSuggestion, Product, Readiness } from "@/lib/api/types";
import { useAction } from "@/hooks/use-action";
import {
  fromBps,
  fromCents,
  OfferAdvisor,
  OfferFields,
  offerValue,
  STORY_MAX,
  toBody,
  toValues,
  type Values,
} from "./campaign-fields";
import { ConfirmDialog } from "./confirm-dialog";

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
      authedApi<CampaignDraft>(`/products/${product.id}/campaign-draft`, { method: "POST", readOnly: true, body: { source_text: text || null } }),
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
  const locked = !!campaign && campaign.status !== "draft";
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
          {locked ? "The offer and prices are locked once a campaign goes live. Copy can still change." : "Everything here is editable. Backers only see it after you publish."}
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
            {locked ? null : (
              <OfferAdvisor
                listCents={dollarsToCents(values.referral_list_price)}
                request={() =>
                  authedApi<OfferSuggestion>(`/products/${product.id}/offer-suggestion`, {
                    method: "POST", readOnly: true,
                    body: {
                      notes: [product.description, values.summary].filter(Boolean).join("\n\n").slice(0, 2000) || null,
                      list_price_cents: dollarsToCents(values.referral_list_price),
                      offer_type: values.offer_type,
                      offer_value: offerValue(values),
                      referral_months: Number(values.referral_months) || 12,
                    },
                  })
                }
                onApply={(o) =>
                  setValues((v) => ({
                    ...v,
                    founding_price: fromCents(o.founding_price_cents),
                    founding_spots_cap: String(o.founding_spots_cap),
                    referral_months: String(o.referral_months),
                    referral_discount: fromBps(o.referral_discount_bps),
                    commission: fromBps(o.commission_bps),
                  }))
                }
              />
            )}
            <FieldSet>
              <FieldLegend>Founding offer</FieldLegend>
              <FieldDescription>One payment buys one reward. Pick the reward, then set what founding backers and their friends pay.</FieldDescription>
              <OfferFields values={values} set={set} onOfferChange={(o) => setValues((v) => ({ ...v, ...o }))} feeBps={feeBps} disabled={locked} />
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

function ReadinessPanel({ campaign, onPublished }: { campaign: Campaign; onPublished: () => void }) {
  const { data: readiness, reload: load } = useApi<Readiness>(campaign.status !== "draft" ? null : `/campaigns/${campaign.id}/readiness`);
  const { pending, run } = useAction();
  const [confirming, setConfirming] = useState(false);

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

  async function end() {
    const ok = await run("end", () => authedApi(`/campaigns/${campaign.id}/end`, { method: "POST" }), "Campaign ended");
    if (ok) {
      setConfirming(false);
      onPublished();
    }
  }

  if (campaign.status === "closed") {
    return (
      <Card size="sm" className="h-fit xl:sticky xl:top-6">
        <CardHeader>
          <CardTitle>Ended</CardTitle>
          <CardDescription>
            Closed to new purchases{campaign.ended_at ? ` on ${shortDate(campaign.ended_at)}` : ""}. {campaign.founding_spots_taken} founding{" "}
            {campaign.founding_spots_taken === 1 ? "backer keeps" : "backers keep"} their access and earned rewards.
          </CardDescription>
        </CardHeader>
      </Card>
    );
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
        <CardContent>
          <ConfirmDialog
            open={confirming}
            onOpenChange={setConfirming}
            trigger={<Button variant="outline" className="w-full">End campaign</Button>}
            title="End this campaign?"
            description="Nobody can buy after this, and it can’t be reopened. Current backers keep their access and codes, and rewards they’ve already earned still pay out."
            confirmLabel="End campaign"
            destructive
            pending={pending === "end"}
            onConfirm={end}
          />
        </CardContent>
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
