"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { ErrorState } from "@/components/backit/error-state";
import { PageHeader } from "@/components/backit/page-header";
import { StatusBadge } from "@/components/backit/status-badge";
import { authedApi, useApi } from "@/hooks/use-api";
import { useAction } from "@/hooks/use-action";
import type { Me, Profile } from "@/lib/api/types";

export default function SettingsPage() {
  const { data, error, loading, reload } = useApi<Me>("/me");
  const [name, setName] = useState("");
  const [payout, setPayout] = useState("");
  const { pending, run } = useAction();

  useEffect(() => {
    if (!data) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setName(data.profile.display_name);
    setPayout(data.profile.payout_email ?? "");
  }, [data]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    const res = await run(
      "save",
      () => authedApi<Profile>("/me", { method: "PATCH", body: { display_name: name.trim(), payout_email: payout.trim() || null } }),
      "Settings saved",
    );
    if (res) reload();
  }

  if (error) return <ErrorState error={error} onRetry={reload} />;

  return (
    <>
      <PageHeader title="Settings" />
      {loading && !data ? (
        <Skeleton className="h-64 max-w-xl" />
      ) : data ? (
        <form onSubmit={save} className="max-w-xl">
          <Card>
            <CardHeader>
              <CardTitle>Profile and payouts</CardTitle>
              <CardDescription>Signed in as {data.profile.email}</CardDescription>
            </CardHeader>
            <CardContent>
              <FieldGroup>
                <Field>
                  <FieldLabel htmlFor="name">Display name</FieldLabel>
                  <Input id="name" required maxLength={120} value={name} onChange={(e) => setName(e.target.value)} />
                  <FieldDescription>Shown to builders and on referral pages. Public ledgers never show names.</FieldDescription>
                </Field>
                <Field>
                  <div className="flex items-center justify-between gap-2">
                    <FieldLabel htmlFor="payout">PayPal email for commissions</FieldLabel>
                    {data.profile.payout_email ? (
                      <StatusBadge status={data.profile.payout_email_verified ? "verified" : "pending"} />
                    ) : null}
                  </div>
                  <Input id="payout" type="email" value={payout} onChange={(e) => setPayout(e.target.value)} placeholder="you@example.com" />
                  <FieldDescription>Use a PayPal sandbox personal account email. Payable commissions without one roll over to the next payout.</FieldDescription>
                </Field>
              </FieldGroup>
            </CardContent>
            <CardFooter>
              <Button type="submit" disabled={pending === "save"}>
                {pending === "save" ? <Spinner data-icon="inline-start" /> : null}
                Save changes
              </Button>
            </CardFooter>
          </Card>
        </form>
      ) : null}
    </>
  );
}
