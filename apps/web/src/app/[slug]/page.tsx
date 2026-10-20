import type { Metadata } from "next";
import Link from "next/link";
import { headers } from "next/headers";
import { ArrowUpRightIcon } from "lucide-react";
import { SiteFooter } from "@/components/backit/site-footer";
import { SiteHeader } from "@/components/backit/site-header";
import { BuyPanel } from "@/components/public/buy-panel";
import { TrustCard } from "@/components/public/trust-card";
import { auth } from "@/lib/auth";
import { getPublicCampaign } from "@/lib/api/server";

export async function generateMetadata({ params }: PageProps<"/[slug]">): Promise<Metadata> {
  const { slug } = await params;
  const c = await getPublicCampaign(slug);
  return { title: `${c.product.name}: ${c.headline}`, description: c.summary };
}

export default async function CampaignPage({ params, searchParams }: PageProps<"/[slug]">) {
  const { slug } = await params;
  const sp = await searchParams;
  const ref = typeof sp.ref === "string" ? sp.ref : undefined;
  const [c, session] = await Promise.all([
    getPublicCampaign(slug, ref),
    auth.api.getSession({ headers: await headers() }).catch(() => null),
  ]);

  return (
    <div className="flex min-h-svh flex-col">
      <SiteHeader />
      <main className="page-shell grid gap-12 py-10 md:grid-cols-[1fr_24rem] md:grid-rows-[auto_1fr] md:gap-x-16 md:gap-y-12 md:py-16">
        <header className="stagger flex min-w-0 flex-col gap-5 md:col-start-1">
            <a
              href={c.product.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex w-fit items-center gap-1 rounded-full bg-muted px-3 py-1 text-sm font-medium text-link transition-colors duration-150 hover:bg-secondary/60"
            >
              {c.product.name}
              <ArrowUpRightIcon className="size-3.5" />
            </a>
            <h1 className="text-5xl leading-[1.02] sm:text-6xl">{c.headline}</h1>
            <p className="max-w-prose text-xl text-pretty text-muted-foreground">{c.summary}</p>
            <p className="text-sm text-muted-foreground">
              Built by <span className="text-foreground">{c.builder_name}</span>
              {c.stats.backers ? (
                <>
                  {" · "}
                  <span className="tabular">{c.stats.backers}</span> {c.stats.backers === 1 ? "backer" : "backers"} so far
                </>
              ) : null}
            </p>
        </header>
        <aside className="rise [animation-delay:150ms] md:sticky md:top-24 md:col-start-2 md:row-span-2 md:row-start-1 md:self-start">
          <BuyPanel campaign={c} referralCode={c.referrer ? c.referrer.code : undefined} signedIn={Boolean(session)} />
        </aside>
        <article className="flex min-w-0 flex-col gap-8 md:col-start-1">
          <div className="max-w-prose font-serif text-[1.1875rem] leading-[1.7] whitespace-pre-line">{c.story}</div>
          <TrustCard campaign={c} />
          <p className="text-sm">
            <Link href={`/${c.slug}/ledger`} className="text-link underline underline-offset-4">
              View the public ledger
            </Link>{" "}
            <span className="text-muted-foreground">for every sale, refund, commission, and payout on this campaign.</span>
          </p>
        </article>
      </main>
      <SiteFooter />
    </div>
  );
}
