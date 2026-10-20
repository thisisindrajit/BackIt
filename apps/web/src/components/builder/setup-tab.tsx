"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { InputGroup, InputGroupAddon, InputGroupInput, InputGroupText } from "@/components/ui/input-group";
import { Spinner } from "@/components/ui/spinner";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { StatusBadge } from "@/components/backit/status-badge";
import { authedApi } from "@/hooks/use-api";
import { dollarsToCents, money, monthLabel, shortDate } from "@/lib/format";
import type { Product, WebhookDelivery } from "@/lib/api/types";
import { CopyField } from "./secret-reveal";
import { useAction } from "@/hooks/use-action";

export function SetupTab({ product, onChange }: { product: Product; onChange: () => void }) {
  const { pending, run } = useAction();
  const [secret, setSecret] = useState<string | null>(null);
  const [months, setMonths] = useState(["2100", "2350", "2400"]);
  const seller = product.seller;
  const v = product.verification;

  async function connect() {
    const res = await run("connect", () =>
      authedApi<{ status: string; action_url: string | null }>(`/products/${product.id}/paypal/onboarding`, { method: "POST" }),
    );
    if (res?.action_url) window.open(res.action_url, "_blank", "noopener");
    onChange();
  }

  async function verify(event: React.FormEvent) {
    event.preventDefault();
    const cents = months.map(dollarsToCents);
    if (cents.some((c) => Number.isNaN(c) || c < 0)) return;
    await run("verify", () => authedApi(`/products/${product.id}/verification/demo`, { method: "POST", body: { months: cents } }), "Revenue evidence saved");
    onChange();
  }

  async function saveWebhook(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const url = String(new FormData(event.currentTarget).get("webhook_url") ?? "").trim();
    await run("webhook", () => authedApi(`/products/${product.id}`, { method: "PATCH", body: { webhook_url: url || null } }), "Webhook URL saved");
    onChange();
  }

  async function testWebhook() {
    const d = await run("test", () => authedApi<WebhookDelivery>(`/products/${product.id}/webhook-test`, { method: "POST" }));
    if (!d) return;
    if (d.state === "delivered") toast.success("Ping delivered");
    else toast.message(`Ping ${d.state}. Details are in the Webhooks tab.`);
  }

  async function rotate() {
    const res = await run("rotate", () => authedApi<{ webhook_secret: string }>(`/products/${product.id}/webhook-secret/rotate`, { method: "POST" }), "Secret rotated");
    if (res) setSecret(res.webhook_secret);
    onChange();
  }

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>1. Get paid through PayPal</CardTitle>
          <CardDescription>Backers pay you directly. BackIt takes its fee at checkout through PayPal’s platform flow.</CardDescription>
          <CardAction>
            <StatusBadge status={seller.status} />
          </CardAction>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {seller.status === "connected" ? (
            <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-[auto_1fr]">
              <dt className="text-muted-foreground">Merchant ID</dt>
              <dd className="font-mono">{seller.merchant_id}</dd>
              <dt className="text-muted-foreground">Can receive payments</dt>
              <dd>{seller.payments_receivable ? "Yes" : "No"}</dd>
              <dt className="text-muted-foreground">Source</dt>
              <dd>{seller.provider === "mock" ? "Mock seller (local demo, no PayPal call)" : "PayPal sandbox"}</dd>
            </dl>
          ) : (
            <p className="text-sm text-muted-foreground">
              {seller.status === "pending" ? "Finish onboarding in the PayPal tab, then refresh the status here." : "You need a connected seller account before publishing."}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            {seller.status !== "connected" ? (
              <Button onClick={connect} disabled={pending === "connect"}>
                {pending === "connect" ? <Spinner data-icon="inline-start" /> : null}
                Connect PayPal
              </Button>
            ) : null}
            {seller.status === "pending" ? (
              <Button variant="outline" onClick={() => run("status", () => authedApi(`/products/${product.id}/paypal/status`)).then(onChange)}>
                Refresh status
              </Button>
            ) : null}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>2. Show your revenue</CardTitle>
          <CardDescription>Campaigns need at least {money(100000)} in each of the last three months. Backers see this on your Trust Card.</CardDescription>
          <CardAction>{v ? <StatusBadge status={v.threshold_met ? "completed" : "failed"} className="normal-case" /> : null}</CardAction>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {v ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Month</TableHead>
                  <TableHead className="text-right">Revenue</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {v.months.map((m) => (
                  <TableRow key={m.month}>
                    <TableCell>{monthLabel(m.month)}</TableCell>
                    <TableCell className="tabular text-right">{money(m.revenue_cents)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : null}
          {v ? (
            <p className="text-sm text-muted-foreground">
              {v.is_demo ? "Demo evidence, labelled as such on your public page." : `Verified from ${v.source}.`} Checked {shortDate(v.checked_at)}.
            </p>
          ) : null}
          <form onSubmit={verify}>
            <FieldGroup>
              <div className="grid gap-3 sm:grid-cols-3">
                {months.map((value, i) => (
                  <Field key={i}>
                    <FieldLabel htmlFor={`m${i}`}>{["Two months ago", "Last month", "This month"][i]}</FieldLabel>
                    <InputGroup>
                      <InputGroupAddon>
                        <InputGroupText>$</InputGroupText>
                      </InputGroupAddon>
                      <InputGroupInput
                        id={`m${i}`}
                        inputMode="decimal"
                        value={value}
                        onChange={(e) => setMonths((prev) => prev.map((p, j) => (j === i ? e.target.value : p)))}
                      />
                    </InputGroup>
                  </Field>
                ))}
              </div>
              <FieldDescription>
                Sandbox only: enter demo figures. Real revenue connections (PayPal, Stripe, RevenueCat) come after the hackathon.
              </FieldDescription>
              <Button type="submit" variant={v ? "outline" : "default"} className="self-start" disabled={pending === "verify"}>
                {pending === "verify" ? <Spinner data-icon="inline-start" /> : null}
                {v ? "Update demo evidence" : "Save demo evidence"}
              </Button>
            </FieldGroup>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>3. Grant access automatically</CardTitle>
          <CardDescription>BackIt signs a webhook to your app on every purchase and refund, so access follows real payments.</CardDescription>
          <CardAction>
            <StatusBadge status={product.webhook_url ? "connected" : "not_configured"} />
          </CardAction>
        </CardHeader>
        <CardContent>
          <form onSubmit={saveWebhook}>
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="webhook_url">Webhook URL</FieldLabel>
                <Input id="webhook_url" name="webhook_url" type="url" defaultValue={product.webhook_url ?? ""} placeholder="https://yourapp.com/webhooks/backit" />
                <FieldDescription>
                  Signing secret ends in <span className="font-mono">{product.webhook_secret_hint ?? "····"}</span>. Verify the <span className="font-mono">BackIt-Signature</span> header with HMAC-SHA256 over <span className="font-mono">timestamp.body</span>.
                </FieldDescription>
              </Field>
              {secret ? <CopyField value={secret} label="New webhook secret" /> : null}
              <div className="flex flex-wrap gap-2">
                <Button type="submit" disabled={pending === "webhook"}>
                  {pending === "webhook" ? <Spinner data-icon="inline-start" /> : null}
                  Save
                </Button>
                <Button type="button" variant="outline" onClick={testWebhook} disabled={!product.webhook_url || pending === "test"}>
                  {pending === "test" ? <Spinner data-icon="inline-start" /> : null}
                  Send test ping
                </Button>
                <Button type="button" variant="ghost" onClick={rotate} disabled={pending === "rotate"}>
                  Rotate secret
                </Button>
              </div>
            </FieldGroup>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
