import Link from "next/link";
import { ArrowRightIcon, CheckIcon } from "lucide-react";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { FoundingSeal } from "@/components/backit/founding-seal";
import { SiteFooter } from "@/components/backit/site-footer";
import { SiteHeader } from "@/components/backit/site-header";
import { HeroWords } from "@/components/landing/hero-words";
import { LedgerTicker } from "@/components/landing/ledger-ticker";

const perks = [
  "A numbered founding backer badge",
  "Your own link to share with friends",
  "$20 for every friend who buys with it",
];

const roles = [
  { who: "You, the builder", body: "Make your first sales, and find new customers through people who already trust you." },
  { who: "Your backers", body: "Get your product at a founding price, a numbered badge, and a reward for every friend who buys." },
  { who: "Their friends", body: "Get a discount for buying through someone they know and trust." },
];

const steps = [
  {
    title: "Open your campaign",
    body: "Connect PayPal, add your product, and tell your story. Our assistant helps you write the page. You check every word before it goes live.",
  },
  {
    title: "Early fans buy in",
    body: "Backers buy a numbered founding spot at the price you choose. They pay with PayPal and get access to your product right away.",
  },
  {
    title: "They spread the word",
    body: "Each backer gets their own link. When a friend buys with it, the friend gets a discount and the backer earns a reward.",
  },
  {
    title: "You pay out the rewards",
    body: "We hold each reward for 30 days, in case the friend asks for a refund. Then you see a list of who earned what. Tap approve, and PayPal pays everyone.",
  },
];

const audiences = [
  {
    id: "builders",
    title: "For builders",
    tone: "bg-card shadow-soft ring-1 ring-foreground/[0.06]",
    points: [
      "A campaign page that explains your product",
      "Money up front from people who believe in it",
      "Fans who share your product for you",
      "A clear record of every sale and reward",
    ],
  },
  {
    id: "backers-card",
    title: "For backers",
    tone: "bg-accent text-accent-foreground",
    points: [
      "The product at its founding price",
      "A numbered founding badge that’s yours for good",
      "Your own link to share with friends",
      "A reward every time a friend buys",
    ],
  },
];

const trust = [
  {
    title: (
      <>
        You stay <em>in charge.</em>
      </>
    ),
    body: "We do the busywork and show you who’s owed what. Nobody gets paid until you approve it.",
    tone: "bg-muted",
  },
  {
    title: "A purchase, not an investment.",
    body: "Backers buy your product. They don’t own any part of your company. They only earn by bringing new customers.",
    tone: "bg-accent text-accent-foreground",
  },
  {
    title: (
      <>
        Out in the <em>open.</em>
      </>
    ),
    body: "Every sale, refund and reward shows up on a public ledger for your campaign. Names stay private.",
    tone: "bg-secondary/50",
  },
];

const faqs = [
  {
    q: "What is a founding backer?",
    a: "Someone who buys your product early, before your bigger launch. They get a special price and a numbered badge that shows they were there first.",
  },
  {
    q: "Is this an investment?",
    a: "No. Backers buy your product. They don’t get shares or any part of your company. They only earn a reward when a friend buys with their link.",
  },
  {
    q: "When do backers get their rewards?",
    a: "Rewards wait 30 days in case a purchase is refunded. After that you review them and pay everyone through PayPal with one approval.",
  },
  {
    q: "What happens if someone asks for a refund?",
    a: "You can refund any sale from your dashboard. The buyer loses access, and any reward tied to that sale is cancelled.",
  },
  {
    q: "Do I need a PayPal account?",
    a: "Yes. Builders get paid through PayPal and backers receive their rewards there too. This demo runs in PayPal’s sandbox, so no real money moves.",
  },
];

// Worked example: a $100 product, $60 founding price, 20% friend discount, 25% reward, 8% BackIt fee.
const examples = [
  {
    title: "An early fan buys a founding spot",
    rows: [
      { label: "They pay", value: "$60" },
      { label: "BackIt (8%)", value: "$4.80" },
    ],
    total: { label: "You get", value: "$55.20" },
  },
  {
    title: "A friend buys with their link",
    rows: [
      { label: "Friend pays (20% off)", value: "$80" },
      { label: "Your backer’s reward", value: "$20" },
      { label: "BackIt (8%)", value: "$6.40" },
    ],
    total: { label: "You get", value: "$53.60" },
  },
];

const included = ["No monthly fee", "No setup cost", "You set the price and the reward", "Pay only when you make a sale"];

export default function Home() {
  return (
    <div className="flex min-h-svh flex-col">
      <SiteHeader />
      <main className="flex flex-col">
        <section className="page-shell flex flex-col items-center gap-8 pt-16 pb-14 text-center md:pt-24">
          <HeroWords words={["Turn", "your", "first", "fans", "into", "your", "best"]} accent="salespeople." />
          <p className="rise max-w-xl text-lg text-pretty text-muted-foreground [animation-delay:600ms]">
            Let your earliest fans buy in at a founding price. They share their link and earn a reward for every friend who buys.
          </p>
          <div className="rise flex flex-wrap justify-center gap-3 [animation-delay:700ms]">
            <Button render={<Link href="/sign-up?next=/app/products/new" />} nativeButton={false} size="lg">
              Start a campaign
              <ArrowRightIcon data-icon="inline-end" />
            </Button>
            <Button render={<a href="#pricing" />} nativeButton={false} size="lg" variant="outline">
              See pricing
            </Button>
          </div>
        </section>

        <section className="page-shell">
          <div className="rise grid grid-cols-[minmax(0,1fr)] items-center gap-6 rounded-[2rem] bg-secondary/40 p-2.5 [animation-delay:850ms] sm:p-8 md:grid-cols-[1fr_auto_1fr] md:gap-8 md:p-10">
            <div className="flex flex-col gap-5 rounded-3xl bg-card p-6 text-left shadow-lift ring-1 ring-foreground/[0.06]">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm text-muted-foreground">Ledgerly · by Maya Chen</span>
                <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">Sample</span>
              </div>
              <div className="flex flex-col gap-1.5">
                <h3 className="text-2xl leading-tight">Bookkeeping that closes itself.</h3>
                <p className="text-sm text-muted-foreground">Be one of the first 50 people to back Ledgerly.</p>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="tabular font-heading text-4xl">$60</span>
                <span className="tabular text-muted-foreground line-through">$100</span>
                <span className="text-sm text-muted-foreground">founding price</span>
              </div>
              <div className="flex flex-col gap-2.5">
                <span className="text-sm font-medium">What you get</span>
                <ul className="flex flex-col gap-2 text-sm">
                  {perks.map((perk) => (
                    <li key={perk} className="flex items-start gap-2">
                      <CheckIcon className="mt-0.5 size-4 shrink-0 text-primary-deep" />
                      <span>{perk}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="flex flex-col gap-2">
                <div className="h-2 overflow-hidden rounded-full bg-muted">
                  <div className="h-full w-[30%] origin-left animate-[grow-x_1.2s_var(--ease-out)_1.1s_both] rounded-full bg-primary motion-reduce:animate-none" />
                </div>
                <span className="tabular text-sm text-muted-foreground">15 of 50 founding spots taken</span>
              </div>
              <span aria-hidden className="flex h-11 items-center justify-center rounded-full bg-primary text-[0.9375rem] font-medium text-white">
                Become a founding backer
              </span>
              <span className="-mt-2 text-center text-xs text-muted-foreground">Pay safely with PayPal</span>
            </div>
            <div className="flex justify-center">
              <div className="pop-in [animation-delay:1.2s]">
                <FoundingSeal number={15} size={168} spin />
              </div>
            </div>
            <LedgerTicker />
          </div>
        </section>

        <section className="page-shell grid gap-10 py-24 md:grid-cols-[0.8fr_1.2fr] md:gap-16 md:py-32">
          <h2 className="reveal text-5xl leading-[1.02]">
            BackIt, in <em>plain words.</em>
          </h2>
          <div className="flex flex-col gap-10">
            <p className="reveal text-xl text-pretty">
              BackIt helps you launch with the people who already love what you make. You open a page for your product.
              Your earliest fans buy a founding spot at a special price. Then they tell their friends, and earn a reward each
              time a friend buys.
            </p>
            <ul className="grid gap-3 sm:grid-cols-3">
              {roles.map((r) => (
                <li key={r.who} className="reveal flex flex-col gap-2 rounded-3xl bg-muted p-5">
                  <h3 className="text-xl leading-tight">{r.who}</h3>
                  <p className="text-sm text-muted-foreground">{r.body}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section id="how-it-works" className="page-shell grid scroll-mt-20 gap-10 pb-24 md:grid-cols-[0.8fr_1.2fr] md:gap-16 md:pb-32">
          <h2 className="text-5xl leading-[1.02] md:sticky md:top-28 md:self-start">
            How it <em>works.</em>
          </h2>
          <ol className="flex flex-col">
            {steps.map((s, i) => (
              <li key={s.title} className="reveal grid gap-3 border-t py-8 first:border-t-0 first:pt-0 sm:grid-cols-[14rem_1fr] sm:gap-8">
                <div className="flex items-baseline gap-3">
                  <span className="tabular font-heading text-lg text-primary-deep italic">0{i + 1}</span>
                  <h3 className="text-2xl leading-tight">{s.title}</h3>
                </div>
                <p className="text-muted-foreground">{s.body}</p>
              </li>
            ))}
          </ol>
        </section>

        <section id="why" className="page-shell scroll-mt-20 pb-24 md:pb-32">
          <div className="flex flex-col gap-12 rounded-[2rem] bg-secondary/40 px-2.5 py-14 sm:px-10 sm:py-16 md:py-24">
            <div className="reveal flex flex-col items-center gap-4 text-center">
              <h2 className="text-5xl leading-[1.02]">
                Good for you. <em>Good for your fans.</em>
              </h2>
              <p className="max-w-xl text-lg text-muted-foreground">
                Everyone who joins early gets something real for it, and you get a head start.
              </p>
            </div>
            <div className="grid gap-5 md:grid-cols-2">
              {audiences.map((a) => (
                <div key={a.id} className={`reveal relative flex flex-col gap-6 overflow-hidden rounded-3xl p-5 sm:p-8 ${a.tone}`}>
                  <h3 className="text-3xl leading-tight">{a.title}</h3>
                  <ul className="flex flex-col gap-3">
                    {a.points.map((p) => (
                      <li key={p} className="flex items-start gap-3">
                        <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-primary text-white">
                          <CheckIcon className="size-3" />
                        </span>
                        {p}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="page-shell grid gap-4 pb-24 md:grid-cols-3 md:pb-32">
          {trust.map((t, i) => (
            <div key={i} className={`reveal flex flex-col gap-4 rounded-3xl p-6 md:p-8 ${t.tone}`}>
              <h2 className="text-3xl leading-[1.05] md:text-4xl">{t.title}</h2>
              <p className="opacity-80">{t.body}</p>
            </div>
          ))}
        </section>

        <section id="pricing" className="page-shell scroll-mt-20">
          <div className="flex flex-col gap-12 rounded-[2rem] bg-secondary/40 px-2.5 py-14 sm:px-10 sm:py-16 md:py-24">
            <div className="reveal flex flex-col items-center gap-4 text-center">
              <h2 className="text-5xl leading-[1.02]">
                Free to start. <em>8% when you sell.</em>
              </h2>
              <p className="max-w-xl text-lg text-muted-foreground">
                Here’s an example. Say your product is $100, you offer founding spots at $60, and friends get 20% off.
              </p>
            </div>

            <div className="grid gap-5 md:grid-cols-2">
              {examples.map((ex) => (
                <div key={ex.title} className="reveal flex flex-col gap-5 rounded-3xl bg-card p-5 shadow-soft ring-1 ring-foreground/[0.06] sm:p-8">
                  <h3 className="text-2xl leading-tight">{ex.title}</h3>
                  <dl className="flex flex-col">
                    {ex.rows.map((r) => (
                      <div key={r.label} className="flex items-baseline justify-between gap-4 border-b border-foreground/[0.07] py-3">
                        <dt className="text-muted-foreground">{r.label}</dt>
                        <dd className="tabular font-heading text-xl">{r.value}</dd>
                      </div>
                    ))}
                    <div className="flex items-baseline justify-between gap-4 pt-4">
                      <dt className="font-medium">{ex.total.label}</dt>
                      <dd className="tabular font-heading text-4xl text-primary-deep">{ex.total.value}</dd>
                    </div>
                  </dl>
                </div>
              ))}
            </div>

            <div className="reveal flex flex-col items-center gap-6">
              <ul className="flex flex-wrap justify-center gap-x-6 gap-y-2">
                {included.map((item) => (
                  <li key={item} className="flex items-center gap-2 text-sm">
                    <CheckIcon className="size-4 text-primary-deep" />
                    {item}
                  </li>
                ))}
              </ul>
              <p className="text-sm text-muted-foreground">PayPal’s own payment fees still apply.</p>
            </div>
          </div>
        </section>

        <section id="faq" className="page-shell grid scroll-mt-20 gap-10 py-24 md:grid-cols-[0.8fr_1.2fr] md:gap-16 md:py-32">
          <h2 className="text-5xl leading-[1.02] md:sticky md:top-28 md:self-start">
            Good <em>questions.</em>
          </h2>
          <Accordion className="reveal">
            {faqs.map((f) => (
              <AccordionItem key={f.q} value={f.q}>
                <AccordionTrigger className="text-lg">{f.q}</AccordionTrigger>
                <AccordionContent className="max-w-prose">{f.a}</AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </section>

        <section className="page-shell pb-16">
          <div className="reveal flex flex-col items-center gap-8 overflow-hidden rounded-[2rem] bg-muted px-5 py-20 text-center sm:px-10">
            <FoundingSeal number={1} size={112} spin />
            <h2 className="max-w-3xl text-[clamp(2.5rem,5vw,4rem)] leading-[1.02]">
              Ready to meet your <em>first backers?</em>
            </h2>
            <Button render={<Link href="/sign-up?next=/app/products/new" />} nativeButton={false} size="lg">
              Start a campaign
              <ArrowRightIcon data-icon="inline-end" />
            </Button>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
