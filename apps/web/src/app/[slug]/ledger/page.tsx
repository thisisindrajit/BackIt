import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeftIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { SiteFooter } from "@/components/backit/site-footer";
import { SiteHeader } from "@/components/backit/site-header";
import { getLedger, getPublicCampaign } from "@/lib/api/server";
import { money, shortDate } from "@/lib/format";
import type { LedgerItem } from "@/lib/api/types";

export const metadata: Metadata = { title: "Public ledger" };

const typeLabel: Record<LedgerItem["type"], string> = {
  founding_purchase: "Founding purchase",
  referral_purchase: "Referral purchase",
  refund: "Refund",
  commission_earned: "Commission earned",
  commission_reversed: "Commission reversed",
  payout_paid: "Payout sent",
};

const negative = new Set<LedgerItem["type"]>(["refund", "commission_reversed"]);

export default async function LedgerPage({ params, searchParams }: PageProps<"/[slug]/ledger">) {
  const { slug } = await params;
  const sp = await searchParams;
  const cursor = typeof sp.cursor === "string" ? sp.cursor : undefined;
  const [c, page] = await Promise.all([getPublicCampaign(slug), getLedger(slug, cursor)]);

  return (
    <div className="flex min-h-svh flex-col">
      <SiteHeader />
      <main className="page-shell flex flex-col gap-8 py-10 md:py-16">
        <Button render={<Link href={`/${c.slug}`} />} nativeButton={false} variant="ghost" size="sm" className="-ml-2 self-start">
          <ArrowLeftIcon data-icon="inline-start" />
          {c.product.name}
        </Button>
        <header className="flex flex-col gap-2">
          <h1 className="text-3xl font-semibold">Public ledger</h1>
          <p className="max-w-prose text-muted-foreground">
            Every money event on this campaign, newest first. Buyers and backers stay anonymous; each line has a reference you can quote to the builder.
          </p>
        </header>
        {page.items.length ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Event</TableHead>
                <TableHead className="max-sm:hidden">Reference</TableHead>
                <TableHead className="text-right">Amount</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {page.items.map((i, idx) => (
                <TableRow key={`${i.ref}-${i.type}-${idx}`}>
                  <TableCell className="text-muted-foreground max-sm:whitespace-normal">{shortDate(i.occurred_at)}</TableCell>
                  <TableCell className="max-sm:whitespace-normal">
                    <span className="flex flex-col">
                      {typeLabel[i.type]}
                      <span className="font-mono text-xs text-muted-foreground sm:hidden">{i.ref}</span>
                    </span>
                  </TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground max-sm:hidden">{i.ref}</TableCell>
                  <TableCell className="tabular text-right">
                    {negative.has(i.type) ? "−" : ""}
                    {money(Math.abs(i.amount_cents))}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <Empty className="border">
            <EmptyHeader>
              <EmptyTitle>Nothing recorded yet</EmptyTitle>
              <EmptyDescription>The first founding purchase will appear here.</EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}
        <div className="flex gap-2">
          {cursor ? (
            <Button render={<Link href={`/${c.slug}/ledger`} />} nativeButton={false} variant="outline">
              Newest
            </Button>
          ) : null}
          {page.next_cursor ? (
            <Button render={<Link href={`/${c.slug}/ledger?cursor=${encodeURIComponent(page.next_cursor)}`} />} nativeButton={false} variant="outline">
              Older
            </Button>
          ) : null}
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
