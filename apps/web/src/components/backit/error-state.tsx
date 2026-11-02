import { CircleAlertIcon, RotateCwIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { errorMessage } from "@/lib/api/client";

export function ErrorState({ error, onRetry, title = "Couldn’t load this" }: { error: unknown; onRetry?: () => void; title?: string }) {
  return (
    <div
      role="alert"
      className="flex flex-col items-start gap-4 rounded-3xl border border-destructive/15 bg-destructive/[0.04] p-5 sm:flex-row sm:items-center sm:gap-5 sm:p-6"
    >
      <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-destructive/10 text-destructive">
        <CircleAlertIcon className="size-5" />
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <p className="font-medium text-foreground">{title}</p>
        <p className="text-sm text-pretty text-muted-foreground">{errorMessage(error)}</p>
      </div>
      {onRetry ? (
        <Button variant="outline" onClick={onRetry} className="shrink-0">
          <RotateCwIcon data-icon="inline-start" />
          Try again
        </Button>
      ) : null}
    </div>
  );
}
