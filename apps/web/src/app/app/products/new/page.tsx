"use client";

import { SparklesIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { InputGroup, InputGroupAddon, InputGroupInput, InputGroupText } from "@/components/ui/input-group";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { FormActions, FormSection } from "@/components/backit/form-section";
import { PageHeader } from "@/components/backit/page-header";
import {
  fromBps,
  fromCents,
  OfferAdvisor,
  OfferFields,
  offerValue,
  STORY_MAX,
  toBody,
  type Values,
} from "@/components/builder/campaign-fields";
import { SecretReveal } from "@/components/builder/secret-reveal";
import { authedApi, useInvalidate } from "@/hooks/use-api";
import { useAction } from "@/hooks/use-action";
import { errorMessage } from "@/lib/api/client";
import { dollarsToCents } from "@/lib/format";
import type { CampaignDraft, OfferSuggestion, ProductCreated } from "@/lib/api/types";

type Product = { name: string; url: string; description: string; access_terms: string; refund_terms: string; webhook_url: string };

const FEE_BPS = 800;

const initialCampaign: Values = {
  slug: "",
  headline: "",
  summary: "",
  story: "",
  founding_price: "99",
  founding_spots_cap: "100",
  referral_list_price: "",
  referral_discount: "20",
  commission: "25",
  offer_type: "lifetime",
  offer_value: "",
};

function slugify(name: string) {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40)
    .replace(/-+$/, "");
}

export default function NewCampaignPage() {
  const router = useRouter();
  const invalidate = useInvalidate();
  const [product, setProduct] = useState<Product>({ name: "", url: "", description: "", access_terms: "", refund_terms: "", webhook_url: "" });
  const [values, setValues] = useState<Values>(initialCampaign);
  const [slugEdited, setSlugEdited] = useState(false);
  const [draftSource, setDraftSource] = useState<CampaignDraft["source"] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [created, setCreated] = useState<ProductCreated | null>(null);
  const { pending, run } = useAction();

  const slug = slugEdited ? values.slug : slugify(product.name);
  const setP = (k: keyof Product) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setProduct((p) => ({ ...p, [k]: e.target.value }));
  const setV = (k: keyof Values) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setValues((v) => ({ ...v, [k]: e.target.value }));

  const facts = () => ({
    name: product.name.trim(),
    url: product.url.trim() || null,
    description: product.description.trim(),
    access_terms: product.access_terms.trim(),
    refund_terms: product.refund_terms.trim() || null,
  });
  const canAskAi = product.name.trim().length > 0 && product.description.trim().length > 0;

  function offerOrNull() {
    const o = toBody({ ...values, slug });
    const numbers = [o.founding_price_cents, o.founding_spots_cap, o.referral_list_price_cents, o.referral_discount_bps, o.commission_bps];
    return numbers.every(Number.isFinite) && o.founding_price_cents >= 100 && o.referral_list_price_cents >= 100
      ? {
          founding_price_cents: o.founding_price_cents,
          founding_spots_cap: o.founding_spots_cap,
          referral_list_price_cents: o.referral_list_price_cents,
          referral_discount_bps: o.referral_discount_bps,
          commission_bps: o.commission_bps,
        }
      : null;
  }

  async function writeStory() {
    const d = await run("draft", () =>
      authedApi<CampaignDraft>("/products/campaign-draft", { method: "POST", readOnly: true, body: { product: facts(), offer: offerOrNull() } }),
    );
    if (d) {
      setValues((v) => ({ ...v, headline: d.headline.slice(0, 160), summary: d.summary, story: d.story }));
      setDraftSource(d.source);
      toast.success("Story drafted. Edit anything before you create the campaign.");
    }
  }

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const res = await authedApi<ProductCreated>("/products", {
        method: "POST",
        body: {
          name: product.name.trim(),
          url: product.url.trim(),
          description: product.description.trim(),
          access_terms: product.access_terms.trim(),
          refund_terms: product.refund_terms.trim() || null,
          webhook_url: product.webhook_url.trim() || null,
          campaign: toBody({ ...values, slug }),
        },
      });
      setCreated(res);
      void invalidate("/me");
      toast.success("Campaign created as a draft");
    } catch (e) {
      setError(errorMessage(e));
      window.scrollTo({ top: 0, behavior: "smooth" });
    } finally {
      setSaving(false);
    }
  }

  if (created) {
    return (
      <>
        <PageHeader title="Save your webhook secret" description="BackIt signs every webhook to your product with this secret. It’s shown once." />
        <FormSection title="Webhook secret" description="Store it in your app’s environment. You can rotate it later from the Setup tab.">
          <SecretReveal secret={created.webhook_secret} />
          <Button className="self-start" onClick={() => router.push(`/app/products/${created.id}`)}>
            I’ve saved it, finish setup
          </Button>
        </FormSection>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="New campaign"
        description="Everything in one place: your product, the founding offer and the story. It’s saved as a draft, then you connect PayPal and publish."
      />
      <form onSubmit={onSubmit} className="flex flex-col">
        {error ? (
          <Alert variant="destructive" className="mb-8 rounded-2xl px-4 py-3">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}

        <FormSection title="Product" description="Plain facts work best. The AI drafts from this and can’t invent numbers.">
          <FieldGroup className="grid gap-6 xl:grid-cols-2">
            <Field>
              <FieldLabel htmlFor="name">Product name</FieldLabel>
              <Input id="name" required maxLength={120} placeholder="Shipnote" value={product.name} onChange={setP("name")} />
            </Field>
            <Field>
              <FieldLabel htmlFor="url">Product URL</FieldLabel>
              <Input id="url" type="url" required placeholder="https://shipnote.app" value={product.url} onChange={setP("url")} />
            </Field>
            <Field className="xl:col-span-2">
              <FieldLabel htmlFor="description">What it does</FieldLabel>
              <Textarea id="description" required maxLength={5000} rows={4} value={product.description} onChange={setP("description")} />
              <FieldDescription>Who it’s for, what it solves, and its regular price if it has one.</FieldDescription>
            </Field>
          </FieldGroup>
        </FormSection>

        <FormSection title="What backers get" description="Shown on your campaign page next to the buy button.">
          <FieldGroup className="grid gap-6 xl:grid-cols-2">
            <Field>
              <FieldLabel htmlFor="access_terms">Access</FieldLabel>
              <Textarea id="access_terms" required maxLength={2000} rows={3} placeholder="The Pro plan, including future updates. For a coupon, say what it applies to." value={product.access_terms} onChange={setP("access_terms")} />
            </Field>
            <Field>
              <FieldLabel htmlFor="refund_terms">Refund terms</FieldLabel>
              <Textarea id="refund_terms" maxLength={2000} rows={3} placeholder="Full refund within 30 days, no questions asked." value={product.refund_terms} onChange={setP("refund_terms")} />
              <FieldDescription>Rewards stay on hold for 30 days to cover this window.</FieldDescription>
            </Field>
          </FieldGroup>
        </FormSection>

        <FormSection title="Founding offer" description="One payment buys one reward. Pick the reward, then set what founding backers and their friends pay.">
          {canAskAi ? (
            <OfferAdvisor
              listCents={dollarsToCents(values.referral_list_price)}
              request={() =>
                authedApi<OfferSuggestion>("/products/offer-suggestion", {
                  method: "POST", readOnly: true,
                  body: {
                    product: facts(),
                    list_price_cents: dollarsToCents(values.referral_list_price),
                    offer_type: values.offer_type,
                    offer_value: offerValue(values),
                  },
                })
              }
              onApply={(o) =>
                setValues((v) => ({
                  ...v,
                  founding_price: fromCents(o.founding_price_cents),
                  founding_spots_cap: String(o.founding_spots_cap),
                  referral_discount: fromBps(o.referral_discount_bps),
                  commission: fromBps(o.commission_bps),
                }))
              }
            />
          ) : (
            <p className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
              Add your product name and what it does, and the offer advisor can suggest the numbers.
            </p>
          )}
          <OfferFields values={values} set={setV} onOfferChange={(o) => setValues((v) => ({ ...v, ...o }))} feeBps={FEE_BPS} />
        </FormSection>

        <FormSection
          title="Campaign page"
          description="Write it yourself, or let the AI draft it from your product and offer. It uses your exact prices and never invents users or revenue."
        >
          <div className="flex flex-col gap-3 rounded-lg border border-dashed p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-col gap-0.5">
              <span className="flex items-center gap-2 text-sm font-medium">
                Draft the story with AI
                {draftSource ? <Badge variant="outline">{draftSource === "ai" ? "AI" : "Template"}</Badge> : null}
              </span>
              <span className="text-sm text-muted-foreground">
                {canAskAi ? "Fills the headline, summary and story. Running it again replaces them." : "Add your product name and what it does first."}
              </span>
            </div>
            <Button type="button" variant="outline" className="shrink-0" onClick={writeStory} disabled={!canAskAi || pending === "draft"}>
              {pending === "draft" ? <Spinner data-icon="inline-start" /> : <SparklesIcon data-icon="inline-start" />}
              {draftSource ? "Redraft" : "Draft with AI"}
            </Button>
          </div>
          <Field>
            <FieldLabel htmlFor="slug">Page address</FieldLabel>
            <InputGroup>
              <InputGroupAddon>
                <InputGroupText>backit.club/</InputGroupText>
              </InputGroupAddon>
              <InputGroupInput
                id="slug"
                value={slug}
                onChange={(e) => {
                  setSlugEdited(true);
                  setValues((v) => ({ ...v, slug: e.target.value.toLowerCase() }));
                }}
                required
                pattern="[a-z0-9][a-z0-9\-]{1,38}[a-z0-9]"
                title="3 to 40 lowercase letters, numbers or dashes"
              />
            </InputGroup>
          </Field>
          <Field>
            <FieldLabel htmlFor="headline">Headline</FieldLabel>
            <Input id="headline" value={values.headline} onChange={setV("headline")} required maxLength={160} />
          </Field>
          <Field>
            <FieldLabel htmlFor="summary">Summary</FieldLabel>
            <Textarea id="summary" rows={2} value={values.summary} onChange={setV("summary")} required maxLength={1000} />
          </Field>
          <Field>
            <FieldLabel htmlFor="story">Story</FieldLabel>
            <Textarea id="story" rows={12} value={values.story} onChange={setV("story")} required maxLength={STORY_MAX} className="min-h-64" />
            <FieldDescription className="flex flex-wrap justify-between gap-x-4 gap-y-1">
              <span>Why you’re building this, who it’s for, and what backers help unlock. Markdown supported: ## headings, **bold**, lists, links.</span>
              <span className="tabular shrink-0">
                {values.story.length.toLocaleString()}/{STORY_MAX.toLocaleString()}
              </span>
            </FieldDescription>
          </Field>
        </FormSection>

        <FormSection title="Access delivery" description="Where BackIt sends purchase and refund events so your app can grant access. You can add it later.">
          <Field>
            <FieldLabel htmlFor="webhook_url">Webhook URL</FieldLabel>
            <Input id="webhook_url" type="url" placeholder="https://yourapp.com/webhooks/backit" value={product.webhook_url} onChange={setP("webhook_url")} />
          </Field>
        </FormSection>

        <FormActions>
          <Button type="submit" size="lg" disabled={saving}>
            {saving ? <Spinner data-icon="inline-start" /> : null}
            Create campaign
          </Button>
          <span className="text-sm text-muted-foreground">Saved as a draft. Nothing is public until you publish.</span>
        </FormActions>
      </form>
    </>
  );
}
