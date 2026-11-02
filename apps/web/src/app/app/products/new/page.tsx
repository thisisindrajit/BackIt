"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { FormActions, FormSection } from "@/components/backit/form-section";
import { PageHeader } from "@/components/backit/page-header";
import { SecretReveal } from "@/components/builder/secret-reveal";
import { authedApi, useInvalidate } from "@/hooks/use-api";
import { errorMessage } from "@/lib/api/client";
import type { ProductCreated } from "@/lib/api/types";

export default function NewProductPage() {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<ProductCreated | null>(null);
  const invalidate = useInvalidate();

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const f = new FormData(event.currentTarget);
    const get = (k: string) => String(f.get(k) ?? "").trim();
    setPending(true);
    setError(null);
    try {
      const product = await authedApi<ProductCreated>("/products", {
        method: "POST",
        body: {
          name: get("name"),
          url: get("url"),
          description: get("description"),
          access_terms: get("access_terms"),
          refund_terms: get("refund_terms") || null,
          webhook_url: get("webhook_url") || null,
        },
      });
      setCreated(product);
      void invalidate("/me");
      toast.success("Product added");
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setPending(false);
    }
  }

  if (created) {
    return (
      <>
        <PageHeader title="Save your webhook secret" description="BackIt signs every webhook to your product with this secret. It’s shown once." />
        <FormSection title="Webhook secret" description="Store it in your app’s environment. You can rotate it later from the Setup tab.">
          <SecretReveal secret={created.webhook_secret} />
          <Button className="self-start" onClick={() => router.push(`/app/products/${created.id}`)}>
            I’ve saved it, continue setup
          </Button>
        </FormSection>
      </>
    );
  }

  return (
    <>
      <PageHeader title="Add your product" description="Tell backers what they’re buying. You’ll connect PayPal and draft the campaign next." />
      <form onSubmit={onSubmit} className="flex flex-col">
        {error ? (
          <Alert variant="destructive" className="mb-8 rounded-2xl px-4 py-3">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}
        <FormSection title="Product" description="Plain facts work best. The AI drafts the pitch from this and can’t invent numbers.">
          <FieldGroup className="grid gap-6 xl:grid-cols-2">
            <Field>
              <FieldLabel htmlFor="name">Product name</FieldLabel>
              <Input id="name" name="name" required maxLength={120} placeholder="Shipnote" />
            </Field>
            <Field>
              <FieldLabel htmlFor="url">Product URL</FieldLabel>
              <Input id="url" name="url" type="url" required placeholder="https://shipnote.app" />
            </Field>
            <Field className="xl:col-span-2">
              <FieldLabel htmlFor="description">What it does</FieldLabel>
              <Textarea id="description" name="description" required maxLength={5000} rows={4} />
            </Field>
          </FieldGroup>
        </FormSection>
        <FormSection title="What backers get" description="Shown on your campaign page next to the buy button.">
          <FieldGroup className="grid gap-6 xl:grid-cols-2">
            <Field>
              <FieldLabel htmlFor="access_terms">Access</FieldLabel>
              <Textarea id="access_terms" name="access_terms" required maxLength={2000} rows={3} placeholder="Lifetime access to the Pro plan, including future updates." />
            </Field>
            <Field>
              <FieldLabel htmlFor="refund_terms">Refund terms</FieldLabel>
              <Textarea id="refund_terms" name="refund_terms" maxLength={2000} rows={3} placeholder="Full refund within 30 days, no questions asked." />
              <FieldDescription>Rewards stay on hold for 30 days to cover this window.</FieldDescription>
            </Field>
          </FieldGroup>
        </FormSection>
        <FormSection title="Access delivery" description="Where BackIt sends purchase and refund events so your app can grant access. You can add it later.">
          <Field>
            <FieldLabel htmlFor="webhook_url">Webhook URL</FieldLabel>
            <Input id="webhook_url" name="webhook_url" type="url" placeholder="https://yourapp.com/webhooks/backit" />
          </Field>
        </FormSection>
        <FormActions>
          <Button type="submit" size="lg" disabled={pending}>
            {pending ? <Spinner data-icon="inline-start" /> : null}
            Add product
          </Button>
        </FormActions>
      </form>
    </>
  );
}
