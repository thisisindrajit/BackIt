"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { ErrorState } from "@/components/backit/error-state";
import { FormActions, FormSection } from "@/components/backit/form-section";
import { PageHeader } from "@/components/backit/page-header";
import { FormSectionsSkeleton } from "@/components/backit/skeletons";
import { StatusBadge } from "@/components/backit/status-badge";
import { authedApi, useApi } from "@/hooks/use-api";
import { useAction } from "@/hooks/use-action";
import type { Me, Profile } from "@/lib/api/types";

export default function SettingsPage() {
  const { data, error, reload } = useApi<Me>("/me");

  return (
    <>
      <PageHeader title="Settings" description="How builders and backers see you, and where your rewards are paid." />
      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : data ? (
        <SettingsForm key={data.profile.id} profile={data.profile} onSaved={reload} />
      ) : (
        <FormSectionsSkeleton />
      )}
    </>
  );
}

function SettingsForm({ profile, onSaved }: { profile: Profile; onSaved: () => Promise<void> }) {
  const [name, setName] = useState(profile.display_name);
  const [payout, setPayout] = useState(profile.payout_email ?? "");
  const { pending, run } = useAction();
  const dirty = name.trim() !== profile.display_name || (payout.trim() || null) !== (profile.payout_email ?? null);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    const res = await run(
      "save",
      () => authedApi<Profile>("/me", { method: "PATCH", body: { display_name: name.trim(), payout_email: payout.trim() || null } }),
      "Settings saved",
    );
    if (res) await onSaved();
  }

  return (
    <form onSubmit={save} className="flex flex-col">
      <FormSection title="Profile" description="Shown to builders and on referral pages. Public ledgers never show names.">
        <FieldGroup className="grid gap-6 xl:grid-cols-2">
          <Field>
            <FieldLabel htmlFor="name">Display name</FieldLabel>
            <Input id="name" required maxLength={120} value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field>
            <FieldLabel htmlFor="email">Sign-in email</FieldLabel>
            <Input id="email" value={profile.email} disabled readOnly />
            <FieldDescription>Comes from your Google account.</FieldDescription>
          </Field>
        </FieldGroup>
      </FormSection>
      <FormSection title="Payouts" description="Builders pay your rewards to this PayPal account once the 30-day refund window passes.">
        <FieldGroup className="grid gap-6 xl:grid-cols-2">
          <Field>
            <div className="flex items-center justify-between gap-2">
              <FieldLabel htmlFor="payout">PayPal email</FieldLabel>
              {profile.payout_email ? <StatusBadge status={profile.payout_email_verified ? "verified" : "pending"} /> : null}
            </div>
            <Input id="payout" type="email" value={payout} onChange={(e) => setPayout(e.target.value)} placeholder="you@example.com" />
            <FieldDescription>Use a PayPal sandbox personal account. Rewards without one roll over to the next payout.</FieldDescription>
          </Field>
        </FieldGroup>
      </FormSection>
      <FormActions>
        <Button type="submit" disabled={!dirty || pending === "save"}>
          {pending === "save" ? <Spinner data-icon="inline-start" /> : null}
          Save changes
        </Button>
      </FormActions>
    </form>
  );
}
