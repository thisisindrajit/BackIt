import { ArrowUpRightIcon, CircleCheckIcon, KeyRoundIcon } from "lucide-react";
import { CopyField } from "@/components/builder/secret-reveal";
import { shortDate } from "@/lib/format";

type Props = {
  code: string;
  productName?: string;
  productUrl?: string;
  claimedAt?: string | null;
  revoked?: boolean;
};

export function AccessCode({ code, productName, productUrl, claimedAt, revoked }: Props) {
  const where = productName ?? "the product";

  if (revoked) {
    return (
      <div className="flex items-start gap-3 rounded-2xl border border-dashed p-4 text-sm text-muted-foreground">
        <KeyRoundIcon className="mt-0.5 size-4 shrink-0" aria-hidden />
        <p>This purchase was refunded, so its access code no longer works.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 rounded-2xl bg-accent p-4 text-accent-foreground">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <p className="flex items-center gap-2 text-sm font-medium">
          <KeyRoundIcon className="size-4" aria-hidden />
          Your access code
        </p>
        {claimedAt ? (
          <span className="flex items-center gap-1 text-xs">
            <CircleCheckIcon className="size-3.5 text-primary" aria-hidden />
            Redeemed {shortDate(claimedAt)}
          </span>
        ) : null}
      </div>
      <CopyField value={code} label="Access code" />
      <p className="text-xs">
        {claimedAt ? "Already used to unlock your plan. " : `Enter it in ${where} to unlock your plan. It works once. `}
        {productUrl ? (
          <a href={productUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 underline underline-offset-4">
            Open {where}
            <ArrowUpRightIcon className="size-3" aria-hidden />
          </a>
        ) : null}
      </p>
    </div>
  );
}
