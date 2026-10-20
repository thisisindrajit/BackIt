import { Wordmark } from "./wordmark";

export function SiteFooter() {
  return (
    <footer className="mt-auto border-t">
      <div className="page-shell flex flex-col gap-4 py-10 text-sm text-muted-foreground md:flex-row md:items-center md:justify-between">
        <Wordmark />
        <div className="flex flex-col gap-1 md:items-end">
          <p>Runs in PayPal sandbox for the PayPal AI Hackathon. No real money moves.</p>
          <p>Backers earn from purchases and referrals only. No equity, no investment returns.</p>
        </div>
      </div>
    </footer>
  );
}
