"use client";

import Link from "next/link";
import { useState } from "react";
import { SparklesIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldLabel } from "@/components/ui/field";
import { Spinner } from "@/components/ui/spinner";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Stat } from "@/components/backit/stat";
import { FoundingSeal } from "@/components/backit/founding-seal";
import { StatusBadge } from "@/components/backit/status-badge";
import { CopyField } from "@/components/builder/secret-reveal";
import { authedApi } from "@/hooks/use-api";
import { useAction } from "@/hooks/use-action";
import { money, shortDate } from "@/lib/format";
import type { Backing, ShareDrafts } from "@/lib/api/types";

type Channel = "x" | "linkedin" | "email";
const channelLabel: Record<Channel, string> = { x: "X", linkedin: "LinkedIn", email: "Email" };

export function BackingCard({ backing: b }: { backing: Backing }) {
  const [channel, setChannel] = useState<Channel>("x");
  const [context, setContext] = useState("");
  const [drafts, setDrafts] = useState<ShareDrafts | null>(null);
  const { pending, run } = useAction();

  async function draft() {
    const res = await run("draft", () =>
      authedApi<ShareDrafts>(`/backings/${b.id}/share-drafts`, { method: "POST", body: { channel, context: context || null } }),
    );
    if (res) setDrafts(res);
  }

  return (
    <Card className="rounded-3xl">
      <CardHeader>
        <CardTitle className="font-display text-2xl">{b.campaign.product_name}</CardTitle>
        <CardDescription>
          <Link href={`/${b.campaign.slug}`} className="text-link underline-offset-4 hover:underline">
            {b.campaign.headline}
          </Link>
        </CardDescription>
        <CardAction>
          {b.badge_number ? (
            <FoundingSeal number={b.badge_number} size={72} className="pop-in" />
          ) : (
            <Badge variant="outline">Referral buyer</Badge>
          )}
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-8">
        <div className="flex flex-col gap-2">
          <p className="text-sm font-medium">Your referral link</p>
          <CopyField value={b.share_url} label="Referral link" />
          <p className="text-xs text-muted-foreground">
            Buyers get a discount, you earn a commission. Commissions are held 30 days in case of refunds, then paid by the builder through PayPal.
          </p>
        </div>

        <dl className="grid grid-cols-2 gap-6 sm:grid-cols-5">
          <Stat label="On hold" value={money(b.balances.held_cents)} />
          <Stat label="Payable" value={money(b.balances.payable_cents)} />
          <Stat label="In a payout" value={money(b.balances.reserved_cents)} />
          <Stat label="Paid" value={money(b.balances.paid_cents)} />
          <Stat label="Reversed" value={money(b.balances.reversed_cents)} />
        </dl>

        {b.commissions.length ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Sale</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="max-sm:hidden">Releases</TableHead>
                <TableHead className="text-right">Commission</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {b.commissions.map((c) => (
                <TableRow key={c.id}>
                  <TableCell className="font-mono text-xs max-sm:whitespace-normal max-sm:break-all">{c.order_ref}</TableCell>
                  <TableCell>
                    <StatusBadge status={c.state} />
                  </TableCell>
                  <TableCell className="text-muted-foreground max-sm:hidden">{c.state === "held" ? shortDate(c.release_at) : "Released"}</TableCell>
                  <TableCell className="tabular text-right">{money(c.amount_cents)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <p className="text-sm text-muted-foreground">No referral sales yet. Commissions appear here as soon as someone buys through your link.</p>
        )}

        <section className="flex flex-col gap-4 rounded-lg bg-muted p-4">
          <div className="flex flex-col gap-1">
            <h3 className="flex items-center gap-2 font-medium">
              <SparklesIcon className="size-4" />
              Draft a post
            </h3>
            <p className="text-sm text-muted-foreground">The agent writes a disclosed, honest recommendation. Edit it before you share.</p>
          </div>
          <Tabs value={channel} onValueChange={(v) => setChannel(v as Channel)}>
            <TabsList>
              {(Object.keys(channelLabel) as Channel[]).map((c) => (
                <TabsTrigger key={c} value={c}>
                  {channelLabel[c]}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          <Field>
            <FieldLabel htmlFor={`ctx-${b.id}`}>Why you backed it (optional)</FieldLabel>
            <Textarea
              id={`ctx-${b.id}`}
              value={context}
              maxLength={1000}
              onChange={(e) => setContext(e.target.value)}
              placeholder="I've used it for invoicing since the beta…"
              className="bg-background"
            />
          </Field>
          <Button onClick={draft} disabled={pending === "draft"} variant="outline" className="self-start bg-background">
            {pending === "draft" ? <Spinner data-icon="inline-start" /> : <SparklesIcon data-icon="inline-start" />}
            Draft {channelLabel[channel]} post
          </Button>
          {drafts?.drafts.map((d, i) => (
            <div key={i} className="flex flex-col gap-2">
              <Textarea defaultValue={d.text} className="min-h-28 bg-background" aria-label={`${channelLabel[d.channel]} draft`} />
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Badge variant="outline">{drafts.source === "ai" ? "AI" : "Template"}</Badge>
                Includes your link and a disclosure that you earn a commission.
              </div>
            </div>
          ))}
        </section>
      </CardContent>
    </Card>
  );
}
