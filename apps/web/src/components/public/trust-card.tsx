import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { money, monthLabel, percent, shortDate } from "@/lib/format";
import type { PublicCampaign } from "@/lib/api/types";

export function TrustCard({ campaign: c }: { campaign: PublicCampaign }) {
  const v = c.trust.verification;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Before you back this</CardTitle>
        <CardDescription>What BackIt checked, and how the money works.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-6 text-sm">
        <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-[10rem_1fr]">
          <dt className="text-muted-foreground">Revenue</dt>
          <dd className="flex flex-col gap-2">
            {v ? (
              <>
                <span className="flex flex-wrap items-center gap-2">
                  {v.threshold_met ? `Above ${money(v.threshold_cents)} a month` : `Below ${money(v.threshold_cents)} a month`}
                  {v.is_demo ? <Badge variant="outline">Demo data, not verified</Badge> : <Badge variant="secondary">Verified via {v.source}</Badge>}
                </span>
                <span className="flex flex-wrap gap-x-4 gap-y-1 text-muted-foreground">
                  {v.months.map((m) => (
                    <span key={m.month}>
                      {monthLabel(m.month)} <span className="tabular text-foreground">{money(m.revenue_cents)}</span>
                    </span>
                  ))}
                </span>
                <span className="text-xs text-muted-foreground">Checked {shortDate(v.checked_at)}</span>
              </>
            ) : (
              "Not checked"
            )}
          </dd>
          <dt className="text-muted-foreground">Payments</dt>
          <dd>
            {c.trust.seller_connected ? "Builder's PayPal account connected" : "Builder's PayPal account not connected"}
            {c.trust.seller_provider === "mock" ? <span className="text-muted-foreground"> (simulated)</span> : <span className="text-muted-foreground"> (sandbox)</span>}
          </dd>
          <dt className="text-muted-foreground">You get</dt>
          <dd>{c.trust.access_terms}</dd>
          <dt className="text-muted-foreground">Refunds</dt>
          <dd>{c.trust.refund_terms || "Refunds are issued by the builder through PayPal. Commissions on refunded sales are reversed."}</dd>
          <dt className="text-muted-foreground">BackIt fee</dt>
          <dd>{percent(c.platform_fee_bps)} of each purchase, paid by the builder</dd>
          <dt className="text-muted-foreground">Referral earnings</dt>
          <dd>
            {percent(c.referral.commission_bps)} of what each referred buyer pays, held {c.trust.hold_days} days for refunds, paid via PayPal once you reach{" "}
            {money(c.trust.payout_minimum_cents)}.
          </dd>
        </dl>
        <p className="rounded-lg bg-accent px-3 py-2 text-accent-foreground">
          Backing is a purchase of the product, not an investment. You get no equity or share of the company. You earn only from sales you refer.
        </p>
      </CardContent>
    </Card>
  );
}
