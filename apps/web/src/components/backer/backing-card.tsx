"use client";

import Link from "next/link";
import { useState } from "react";
import { SparklesIcon } from "lucide-react";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
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
import { AccessCode } from "@/components/backer/access-code";
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
  const { held_cents, payable_cents, reserved_cents, paid_cents } = b.balances;
  const earned = held_cents + payable_cents + reserved_cents + paid_cents;

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
          <span className="mt-1 block text-xs">
            by {b.campaign.builder_name} · Backed {shortDate(b.created_at)}
          </span>
        </CardDescription>
        <CardAction>
          {b.badge_number ? (
            <FoundingSeal number={b.badge_number} size={72} className="pop-in" />
          ) : (
            <Badge variant="outline">Referral buyer</Badge>
          )}
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        <AccessCode
          code={b.claim_code}
          productName={b.campaign.product_name}
          productUrl={b.campaign.product_url}
          claimedAt={b.claimed_at}
          revoked={b.status === "revoked"}
        />
        <div className="flex flex-col gap-2">
          <p className="text-sm font-medium">Your referral link</p>
          <CopyField value={b.share_url} label="Referral link" />
          <p className="text-xs text-muted-foreground">Friends get a discount and you earn a reward, paid after the 30-day refund window.</p>
        </div>

        <dl className="grid grid-cols-3 gap-4 sm:max-w-md">
          <Stat label="Earned" value={money(earned)} />
          <Stat label="On hold" value={money(b.balances.held_cents)} />
          <Stat label="Paid to you" value={money(b.balances.paid_cents)} />
        </dl>

        <Accordion className="border-t">
          <AccordionItem value="sales">
            <AccordionTrigger>Referral sales ({b.commissions.length})</AccordionTrigger>
            <AccordionContent>
              {b.commissions.length ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Status</TableHead>
                      <TableHead>Releases</TableHead>
                      <TableHead className="text-right">Reward</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {b.commissions.map((c) => (
                      <TableRow key={c.id}>
                        <TableCell>
                          <StatusBadge status={c.state} />
                        </TableCell>
                        <TableCell>{c.state === "held" ? shortDate(c.release_at) : "Released"}</TableCell>
                        <TableCell className="tabular text-right text-foreground">{money(c.amount_cents)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <p className="text-sm">No referral sales yet. They show up here as soon as someone buys through your link.</p>
              )}
            </AccordionContent>
          </AccordionItem>
          <AccordionItem value="post">
            <AccordionTrigger>
              <span className="flex items-center gap-2">
                <SparklesIcon className="size-4" aria-hidden />
                Draft a post
              </span>
            </AccordionTrigger>
            <AccordionContent className="flex flex-col gap-4">
              <p className="text-sm">The agent writes an honest recommendation with a disclosure. Edit it before you share.</p>
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
                />
              </Field>
              <Button onClick={draft} disabled={pending === "draft"} variant="outline" className="self-start">
                {pending === "draft" ? <Spinner data-icon="inline-start" /> : <SparklesIcon data-icon="inline-start" />}
                Draft {channelLabel[channel]} post
              </Button>
              {drafts?.drafts.map((d, i) => (
                <div key={i} className="flex flex-col gap-2">
                  <Textarea defaultValue={d.text} className="min-h-28 text-foreground" aria-label={`${channelLabel[d.channel]} draft`} />
                  <div className="flex items-center gap-2 text-xs">
                    <Badge variant="outline">{drafts.source === "ai" ? "AI" : "Template"}</Badge>
                    Includes your link and a disclosure that you earn a reward.
                  </div>
                </div>
              ))}
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </CardContent>
    </Card>
  );
}
