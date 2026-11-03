"use client";

import { useState } from "react";
import { toast } from "sonner";
import { PauseIcon, ShieldCheckIcon, SparklesIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Field, FieldLabel } from "@/components/ui/field";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ErrorState } from "@/components/backit/error-state";
import { StatusBadge } from "@/components/backit/status-badge";
import { authedApi, useApi } from "@/hooks/use-api";
import { CardsSkeleton } from "@/components/backit/skeletons";
import { useConfig } from "@/hooks/use-config";
import { money, shortDate } from "@/lib/format";
import type { PayoutBatch, PayoutPreview, RiskAssessment } from "@/lib/api/types";
import { ConfirmDialog } from "./confirm-dialog";
import { useAction } from "@/hooks/use-action";

const reasons: Record<string, string> = {
  below_minimum: "Below the $1 minimum, rolls over",
  in_hold: "Still in the 30-day refund hold",
  no_payout_email: "No verified payout email yet",
  risk_review: "Held for review",
  refund_pending: "Refund pending",
};

export function PayoutsTab({ productId }: { productId: string }) {
  const config = useConfig();
  const batches = useApi<PayoutBatch[]>(`/products/${productId}/payout-batches`);
  const [preview, setPreview] = useState<PayoutPreview | null>(null);
  const [funding, setFunding] = useState(false);
  const [open, setOpen] = useState(false);
  const { pending, run } = useAction();

  async function prepare() {
    const p = await run("prepare", () => authedApi<PayoutPreview>(`/products/${productId}/payout-previews`, { method: "POST" }));
    if (p) {
      setPreview(p);
      setFunding(false);
    }
  }

  async function approve() {
    if (!preview) return;
    const batch = await run(
      "approve",
      () =>
        authedApi<PayoutBatch>(`/payout-previews/${preview.id}/approve`, {
          method: "POST",
          body: { digest: preview.digest, funding_confirmed: funding },
          idempotencyKey: `approve-${preview.id}`,
        }),
      "Payout approved and queued",
    );
    setOpen(false);
    if (batch) {
      setPreview(null);
      batches.reload();
    }
  }

  async function hold(backingId: string, name: string) {
    if (!preview) return;
    const p = await run(
      `hold-${backingId}`,
      () => authedApi<PayoutPreview>(`/payout-previews/${preview.id}/hold`, { method: "POST", body: { backing_id: backingId } }),
      `${name} held for review. Decide under Webhooks → Review flags.`,
    );
    if (p) {
      setPreview(p);
      setFunding(false);
    }
  }

  async function releaseHolds() {
    const res = await run("release", () => authedApi<{ released: number }>(`/products/${productId}/dev/release-holds`, { method: "POST" }));
    if (res) toast.success(`${res.released} ${res.released === 1 ? "commission" : "commissions"} released from hold`);
  }

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex max-w-prose flex-col gap-1">
          <h2 className="text-2xl">Pay your backers</h2>
          <p className="text-sm text-muted-foreground">
            The payout agent gathers commissions past their 30-day hold, explains what’s excluded, and freezes an exact preview. Nothing is sent until you approve it.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {config?.environment === "development" ? (
            <Button variant="ghost" onClick={releaseHolds} disabled={pending === "release"}>
              Skip hold (demo)
            </Button>
          ) : null}
          <Button onClick={prepare} disabled={pending === "prepare"}>
            {pending === "prepare" ? <Spinner data-icon="inline-start" /> : <SparklesIcon data-icon="inline-start" />}
            Prepare payout
          </Button>
        </div>
      </div>

      {preview ? (
        <Card>
          <CardHeader>
            <CardTitle>Payout preview</CardTitle>
            <CardDescription>
              Frozen {shortDate(preview.created_at)}. If anything changes before you approve, you’ll be asked to prepare a new one.
            </CardDescription>
            <CardAction>
              <StatusBadge status={preview.status} />
            </CardAction>
          </CardHeader>
          <CardContent className="flex flex-col gap-6">
            <div className="flex flex-col gap-2 rounded-lg bg-muted p-4">
              <div className="flex items-center gap-2 text-sm font-medium">
                <SparklesIcon className="size-4" />
                Agent summary
                <Badge variant="outline">{preview.explanation.source === "ai" ? "AI" : "Template"}</Badge>
              </div>
              <p className="text-sm">{preview.explanation.text}</p>
            </div>
            {preview.items.length ? (
              <div className="flex flex-col gap-2">
                <div className="flex flex-wrap items-center gap-2 text-sm font-medium">
                  <ShieldCheckIcon className="size-4" />
                  Risk review
                  <Badge variant="outline">{preview.risk_source === "ai" ? "AI" : "Rules"}</Badge>
                </div>
                <p className="text-sm text-muted-foreground">
                  Each backer’s referral pattern is checked before money moves. The review only recommends; you decide who gets held.
                </p>
                <ul className="flex flex-col divide-y rounded-lg border">
                  {preview.items.map((i) => (
                    <RiskRow
                      key={i.backing_id}
                      name={i.backer_name}
                      risk={i.risk ?? null}
                      pending={pending === `hold-${i.backing_id}`}
                      disabled={preview.status !== "open"}
                      onHold={() => hold(i.backing_id, i.backer_name)}
                    />
                  ))}
                </ul>
              </div>
            ) : null}
            {preview.items.length ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Backer</TableHead>
                    <TableHead className="max-sm:hidden">PayPal email</TableHead>
                    <TableHead className="text-right max-sm:hidden">Commissions</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {preview.items.map((i) => (
                    <TableRow key={i.backing_id}>
                      <TableCell>{i.backer_name}</TableCell>
                      <TableCell className="text-muted-foreground max-sm:hidden">{i.payout_email_masked}</TableCell>
                      <TableCell className="tabular text-right max-sm:hidden">{i.commission_ids.length}</TableCell>
                      <TableCell className="tabular text-right">{money(i.amount_cents)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
                <TableFooter>
                  <TableRow>
                    <TableCell colSpan={3} className="max-sm:hidden">Total</TableCell>
                    <TableCell className="sm:hidden">Total</TableCell>
                    <TableCell className="tabular text-right">{money(preview.total_cents)}</TableCell>
                  </TableRow>
                </TableFooter>
              </Table>
            ) : (
              <p className="text-sm text-muted-foreground">Nothing is payable right now.</p>
            )}
            {preview.exclusions.length ? (
              <div className="flex flex-col gap-2">
                <h3 className="text-sm font-medium">Not included</h3>
                <ul className="flex flex-col divide-y rounded-lg border text-sm">
                  {preview.exclusions.map((e, idx) => (
                    <li key={`${e.backing_id}-${e.reason}-${idx}`} className="flex items-center justify-between gap-3 px-3 py-2">
                      <span className="flex flex-col">
                        <span>{e.backer_name}</span>
                        <span className="text-muted-foreground">{reasons[e.reason] ?? e.reason}</span>
                      </span>
                      <span className="tabular">{money(e.amount_cents)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            <Separator />
            <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-[auto_1fr]">
              <dt className="text-muted-foreground">Funded from</dt>
              <dd>Sandbox payout sender (separate from checkout funds)</dd>
              <dt className="text-muted-foreground">Required</dt>
              <dd className="tabular">{money(preview.funding.required_cents)}</dd>
              <dt className="text-muted-foreground">Available</dt>
              <dd className="tabular">{preview.funding.available_cents === null ? "Not visible, confirm below" : money(preview.funding.available_cents)}</dd>
              <dt className="text-muted-foreground">Preview fingerprint</dt>
              <dd className="font-mono text-xs break-all">{preview.digest}</dd>
            </dl>
          </CardContent>
          {preview.items.length && preview.status === "open" ? (
            <CardFooter>
              <ConfirmDialog
                open={open}
                onOpenChange={setOpen}
                trigger={<Button>Approve {money(preview.total_cents)}</Button>}
                title={`Send ${money(preview.total_cents)} to ${preview.items.length} ${preview.items.length === 1 ? "backer" : "backers"}?`}
                description="BackIt rechecks every commission, then sends exactly this batch through PayPal Payouts. Approved payouts can't be recalled."
                confirmLabel="Approve payout"
                pending={pending === "approve"}
                disabled={preview.funding.available_cents === null && !funding}
                onConfirm={approve}
              >
                {preview.funding.available_cents === null ? (
                  <Field orientation="horizontal">
                    <Checkbox id="funding" checked={funding} onCheckedChange={(v) => setFunding(Boolean(v))} />
                    <FieldLabel htmlFor="funding" className="font-normal">
                      I confirm the sandbox payout sender holds at least {money(preview.funding.required_cents)}.
                    </FieldLabel>
                  </Field>
                ) : null}
              </ConfirmDialog>
            </CardFooter>
          ) : null}
        </Card>
      ) : null}

      <section className="flex flex-col gap-3">
        <h2 className="text-2xl">Payout history</h2>
        {batches.error ? (
          <ErrorState error={batches.error} onRetry={batches.reload} />
        ) : !batches.data ? (
          <CardsSkeleton count={1} />
        ) : batches.data.length ? (
          <div className="grid gap-4 xl:grid-cols-2">
            {batches.data.map((b) => (
              <Card key={b.id} size="sm">
                <CardHeader>
                  <CardTitle className="tabular">{money(b.total_cents)}</CardTitle>
                  <CardDescription>
                    Approved {shortDate(b.approved_at)} · <span className="font-mono text-xs break-all">{b.sender_batch_id}</span>
                  </CardDescription>
                  <CardAction>
                    <StatusBadge status={b.status} />
                  </CardAction>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  <ul className="flex flex-col divide-y text-sm">
                    {b.items.map((i) => (
                      <li key={i.id} className="flex items-center justify-between gap-3 py-2">
                        <span>{i.backer_name}</span>
                        <span className="flex items-center gap-3">
                          <span className="tabular">{money(i.amount_cents)}</span>
                          <StatusBadge status={i.status} />
                        </span>
                      </li>
                    ))}
                  </ul>
                  {b.summary ? <p className="text-sm text-muted-foreground">{b.summary}</p> : null}
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <Empty className="border">
            <EmptyHeader>
              <EmptyTitle>No payouts yet</EmptyTitle>
              <EmptyDescription>Commissions become payable 30 days after each sale. Approved batches and their PayPal status appear here.</EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}
      </section>
    </div>
  );
}

const levelTone: Record<RiskAssessment["level"], string> = {
  low: "border-transparent bg-secondary text-secondary-foreground",
  medium: "border-transparent bg-accent text-accent-foreground",
  high: "border-transparent bg-destructive/10 text-destructive",
};

function RiskRow({
  name,
  risk,
  pending,
  disabled,
  onHold,
}: {
  name: string;
  risk: RiskAssessment | null;
  pending: boolean;
  disabled: boolean;
  onHold: () => void;
}) {
  return (
    <li className="flex flex-col gap-2 p-3 sm:flex-row sm:items-start sm:justify-between">
      <div className="flex min-w-0 flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">{name}</span>
          {risk ? (
            <Badge variant="outline" className={`capitalize ${levelTone[risk.level]}`}>
              {risk.level} risk
            </Badge>
          ) : null}
          {risk?.recommendation === "hold" ? <span className="text-xs text-destructive">Suggests holding</span> : null}
        </div>
        {risk ? <p className="text-sm text-muted-foreground">{risk.summary}</p> : null}
        {risk?.signals.length ? (
          <ul className="flex flex-wrap gap-1.5">
            {risk.signals.map((s) => (
              <li key={s} className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                {s}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
      <Button
        variant={risk?.recommendation === "hold" ? "outline" : "ghost"}
        size="sm"
        className="shrink-0 self-start"
        onClick={onHold}
        disabled={pending || disabled}
      >
        {pending ? <Spinner data-icon="inline-start" /> : <PauseIcon data-icon="inline-start" />}
        Hold
      </Button>
    </li>
  );
}
